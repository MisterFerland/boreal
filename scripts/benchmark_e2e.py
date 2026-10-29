"""Measure real HTTP -> workers -> PostgreSQL approval/posting in an isolated database."""

from __future__ import annotations
import hashlib
import json
import os
import platform
import random
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts"), str(ROOT / "backend")]
from client import Client
from fixtures.generate import detail, make_batch, SEED
from local_runtime import config, environment, PORT


def main():
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row

    conf = config()
    target = "boreal_benchmark_" + uuid.uuid4().hex[:8]
    admin_args = {"host": "127.0.0.1", "port": PORT, "user": "boreal_admin", "password": conf["admin"]}
    with psycopg.connect(dbname="postgres", autocommit=True, **admin_args) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {} OWNER boreal_migration").format(sql.Identifier(target)))
    env = environment()
    env.update(
        BOREAL_DATABASE_URL=env["BOREAL_DATABASE_URL"].rsplit("/", 1)[0] + "/" + target,
        BOREAL_MIGRATION_URL=env["BOREAL_MIGRATION_URL"].rsplit("/", 1)[0] + "/" + target,
        BOREAL_ORIGIN="http://127.0.0.1:18001",
        BOREAL_CHUNK_SIZE="500",
        BOREAL_LEASE_SECONDS="60",
    )
    processes = []
    logs = []
    try:
        subprocess.run([sys.executable, "-m", "boreal.manage", "migrate"], env=env, cwd=ROOT, check=True)
        with (
            psycopg.connect(dbname="boreal", **admin_args) as source,
            psycopg.connect(env["BOREAL_MIGRATION_URL"]) as dest,
        ):
            for row in source.execute("SELECT id,username,password_hash,role FROM users"):
                dest.execute("INSERT INTO users(id,username,password_hash,role) VALUES (%s,%s,%s,%s)", row)
        commands = [
            ("api", ["-m", "uvicorn", "boreal.api:app", "--host", "127.0.0.1", "--port", "18001"]),
            ("worker", ["-m", "boreal.worker"]),
        ]
        for name, command in commands:
            log = (ROOT / ".local" / f"benchmark-{name}.log").open("wb")
            logs.append(log)
            processes.append(
                subprocess.Popen([sys.executable, *command], env=env, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            )
        operator, approver = Client("http://127.0.0.1:18001"), Client("http://127.0.0.1:18001")
        for _ in range(60):
            try:
                operator.request("GET", "/health/live")
                break
            except Exception:
                time.sleep(0.5)
        operator.login("operator")
        approver.login("approver")
        results = []
        for count in (100, 10000, 100000):
            rng = random.Random(SEED)
            rows = []
            for i in range(count):
                cents = rng.randint(1, 750000)
                amount = f"{cents // 100}.{cents % 100:02}" if i % 100 != 99 else "0.00"
                rows.append(detail(f"E{count:06}-{i:06}", amount, source="BENCH01"))
            raw = make_batch(rows, f"BENCHMARK-{count}")
            start = time.perf_counter()
            batch = operator.request("POST", "/batches", filename=f"benchmark-{count}.dat", raw=raw)
            operator.wait(batch["job_id"], timeout=600)
            calculated = time.perf_counter()
            review = operator.request("GET", f"/batches/{batch['id']}")
            approver.request("POST", f"/batches/{batch['id']}/approve", {})
            job = approver.request("POST", f"/batches/{batch['id']}/post", {})
            approver.wait(job["id"], timeout=600)
            elapsed = time.perf_counter() - start
            with psycopg.connect(env["BOREAL_DATABASE_URL"], row_factory=dict_row) as conn:
                ledger = conn.execute(
                    "SELECT count(*) AS count,sum(amount)::text AS amount FROM journals WHERE batch_id=%s",
                    (batch["id"],),
                ).fetchone()
                assert ledger["count"] == review["accepted_count"]
            result = {
                "records": count,
                "seed": SEED,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
                "accepted": review["accepted_count"],
                "rejected": review["rejected_count"],
                "calculation_seconds": round(calculated - start, 6),
                "elapsed_seconds": round(elapsed, 6),
                "records_per_second": round(count / elapsed, 2),
                "journals": ledger["count"],
                "posted_amount": ledger["amount"],
            }
            print(json.dumps(result), flush=True)
            if count != 100:
                results.append(result)
        report = {
            "scope": "Real loopback HTTP import, durable COBOL calculation, separate authenticated approval, chunk posting and PostgreSQL commit; polling included.",
            "warmup": "100 rows, same complete flow",
            "repetitions": 1,
            "workers": 1,
            "posting_chunk": 500,
            "hardware": {
                "platform": platform.platform(),
                "logical_cpus": os.cpu_count(),
                "memory": Path("/proc/meminfo").read_text().splitlines()[:3],
            },
            "database": "PostgreSQL 17.11 isolated database, default128MiB shared_buffers",
            "python": sys.version,
            "memory_peak": "Unavailable for full process tree; no memory claim inferred.",
            "results": results,
        }
        (ROOT / "artifacts" / "e2e-benchmarks.json").write_text(json.dumps(report, indent=2))
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for log in logs:
            log.close()
        with psycopg.connect(dbname="postgres", autocommit=True, **admin_args) as conn:
            conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(target)))


if __name__ == "__main__":
    main()
