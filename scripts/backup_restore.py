"""Backup and restore rehearsal against a new, uniquely named local PostgreSQL database."""

from __future__ import annotations
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "scripts")]
from local_runtime import PG_BIN, PORT, config, environment


def main():
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
    from boreal import engine
    from boreal.common import digest, financial_records, verify_audit
    from boreal.worker import apply_reference_snapshot

    started = time.perf_counter()
    conf = config()
    backup_dir = ROOT / ".local" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.chmod(0o700)
    target = "boreal_restore_" + uuid.uuid4().hex[:10]
    args = {
        "host": "127.0.0.1",
        "port": PORT,
        "user": "boreal_admin",
        "password": conf["admin"],
        "row_factory": dict_row,
    }
    query = "SELECT kind,count(*) AS count,sum(amount)::text AS total FROM journals GROUP BY kind ORDER BY kind"
    with psycopg.connect(dbname="boreal", **args) as source:
        baseline = source.execute(query).fetchall()
        inputs = source.execute("SELECT id,source_sha256,raw,engine_build FROM batches ORDER BY id").fetchall()
        build_ids = sorted({row["engine_build"] for row in inputs if row["engine_build"]})
    env = environment()
    env["PGPASSWORD"] = conf["admin"]
    backup = backup_dir / "boreal-backup.zip"
    with tempfile.TemporaryDirectory(prefix="boreal-backup-") as temp:
        dump = Path(temp) / "database.dump"
        subprocess.run(
            [
                str(PG_BIN / "pg_dump"),
                "-h",
                "127.0.0.1",
                "-p",
                str(PORT),
                "-U",
                "boreal_admin",
                "-d",
                "boreal",
                "-Fc",
                "-Z0",
                "--no-owner",
                "-f",
                str(dump),
            ],
            env=env,
            check=True,
        )
        with zipfile.ZipFile(backup, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(dump, "database.dump")
            for build_id in build_ids:
                for path in (ROOT / "engine" / "builds" / build_id).rglob("*"):
                    if path.is_file():
                        archive.write(path, path.relative_to(ROOT))
            archive.writestr(
                "manifest.json",
                json.dumps(
                    {
                        "input_hashes": [row["source_sha256"] for row in inputs],
                        "builds": build_ids,
                        "financial_totals": baseline,
                        "scope": "PRIVATE local database backup, includes account hashes. Never export as public evidence.",
                    }
                ),
            )
        backup.chmod(0o600)
        restored_builds = Path(temp) / "restored" / "engine" / "builds"
        with zipfile.ZipFile(backup) as archive:
            for name in archive.namelist():
                if name.startswith("engine/builds/"):
                    restored_file = Path(temp) / "restored" / name
                    restored_file.parent.mkdir(parents=True, exist_ok=True)
                    restored_file.write_bytes(archive.read(name))
                    restored_file.chmod(0o700)
        with psycopg.connect(dbname="postgres", autocommit=True, **args) as admin:
            admin.execute(sql.SQL("CREATE DATABASE {} OWNER boreal_migration").format(sql.Identifier(target)))
        try:
            subprocess.run(
                [
                    str(PG_BIN / "pg_restore"),
                    "-h",
                    "127.0.0.1",
                    "-p",
                    str(PORT),
                    "-U",
                    "boreal_admin",
                    "-d",
                    target,
                    "--no-owner",
                    "--exit-on-error",
                    str(dump),
                ],
                env=env,
                check=True,
            )
            with psycopg.connect(dbname=target, **args) as restored:
                totals = restored.execute(query).fetchall()
                assert totals == baseline
                rows = restored.execute("SELECT source_sha256,raw FROM batches").fetchall()
                assert all(hashlib.sha256(row["raw"]).hexdigest() == row["source_sha256"] for row in rows)
                assert sorted(row["source_sha256"] for row in rows) == sorted(row["source_sha256"] for row in inputs)
                audit = verify_audit(restored)
                assert audit["valid"]
                batch = restored.execute(
                    "SELECT * FROM batches WHERE status='posted' ORDER BY created_at LIMIT 1"
                ).fetchone()
                previous_build_path = os.environ.get("BOREAL_ENGINE_BUILDS")
                os.environ["BOREAL_ENGINE_BUILDS"] = str(restored_builds)
                try:
                    replay = engine.calculate(batch["raw"], batch["policy"], build_id=batch["engine_build"])
                finally:
                    if previous_build_path is None:
                        os.environ.pop("BOREAL_ENGINE_BUILDS", None)
                    else:
                        os.environ["BOREAL_ENGINE_BUILDS"] = previous_build_path
                replay_records = apply_reference_snapshot(replay["records"], batch["reference_snapshot"])
                replay_digest = digest(financial_records(replay_records))
                assert replay_digest == batch["result_digest"]
                assert restored.execute(query).fetchall() == baseline
            result = {
                "passed": True,
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "financial_totals": totals,
                "inputs_verified": len(rows),
                "retained_builds": build_ids,
                "replay_digest": replay_digest,
                "audit": audit,
                "backup": ".local/backups/boreal-backup.zip",
                "database": "isolated temporary restore database, removed after verification",
            }
            (ROOT / "artifacts" / "backup-restore.json").write_text(json.dumps(result, indent=2))
            print(
                json.dumps({"passed": True, "inputs_verified": len(rows), "elapsed_seconds": result["elapsed_seconds"]})
            )
        finally:
            with psycopg.connect(dbname="postgres", autocommit=True, **args) as admin:
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(target)))


if __name__ == "__main__":
    main()
