"""Optional Linux/WSL runtime without Docker. PostgreSQL is isolated to BOREAL's own cluster."""

from __future__ import annotations
import argparse
import json
import os
import pwd
import secrets
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
PG_BIN = Path(os.environ.get("BOREAL_PG_BIN", "/opt/boreal-tools/pgsql/bin"))
PG_DATA = Path(os.environ.get("BOREAL_PG_DATA", "/opt/boreal-data"))
PORT = 55432


def run(args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def config():
    LOCAL.mkdir(exist_ok=True)
    target = LOCAL / "runtime.json"
    if not target.exists():
        target.write_text(json.dumps({name: secrets.token_urlsafe(32) for name in ("admin", "migration", "runtime")}))
        target.chmod(0o600)
    return json.loads(target.read_text())


def environment():
    conf = config()
    result = dict(os.environ)
    result.update(
        {
            "PATH": f"/opt/boreal-tools/bin:{PG_BIN}:" + result.get("PATH", ""),
            "LD_LIBRARY_PATH": "/opt/boreal-tools/lib",
            "PYTHONPATH": str(ROOT / "backend") + os.pathsep + str(ROOT),
            "BOREAL_DATABASE_URL": f"postgresql://boreal_app:{conf['runtime']}@127.0.0.1:{PORT}/boreal",
            "BOREAL_MIGRATION_URL": f"postgresql://boreal_migration:{conf['migration']}@127.0.0.1:{PORT}/boreal",
            "BOREAL_ORIGIN": "http://127.0.0.1:8000",
            "BOREAL_COOKIE_SECURE": "0",
            "BOREAL_DEMO": "1",
            "BOREAL_LEASE_SECONDS": "8",
        }
    )
    return result


def prepare():
    conf = config()
    if not (PG_BIN / "initdb").exists():
        raise SystemExit("PostgreSQL binaries missing. Set BOREAL_PG_BIN or use Docker bootstrap.")
    if os.getuid() == 0:
        try:
            owner = pwd.getpwnam("boreal_pg")
        except KeyError:
            run(["useradd", "--system", "--home-dir", str(PG_DATA), "--shell", "/bin/false", "boreal_pg"])
            owner = pwd.getpwnam("boreal_pg")
        PG_DATA.mkdir(parents=True, exist_ok=True)
        os.chown(PG_DATA, owner.pw_uid, owner.pw_gid)
        prefix = ["runuser", "-u", "boreal_pg", "--"]
    else:
        prefix = []
        PG_DATA.mkdir(parents=True, exist_ok=True)
    if not (PG_DATA / "PG_VERSION").exists():
        password_file = PG_DATA / "initial-password"
        password_file.write_text(conf["admin"])
        password_file.chmod(0o600)
        if os.getuid() == 0:
            os.chown(password_file, owner.pw_uid, owner.pw_gid)
        # initdb requires an empty directory. Put its temporary password beside the cluster.
        password_file.rename(PG_DATA.with_name(PG_DATA.name + "-password"))
        password_file = PG_DATA.with_name(PG_DATA.name + "-password")
        try:
            run(
                prefix
                + [
                    PG_BIN / "initdb",
                    "-D",
                    PG_DATA,
                    "-U",
                    "boreal_admin",
                    "--auth=scram-sha-256",
                    "--encoding=UTF8",
                    "--locale=C",
                    "--pwfile",
                    password_file,
                ]
            )
        finally:
            password_file.unlink(missing_ok=True)
        with (PG_DATA / "postgresql.conf").open("a") as stream:
            stream.write(f"\nlisten_addresses = '127.0.0.1'\nport = {PORT}\nunix_socket_directories = ''\n")
    status = subprocess.run(prefix + [str(PG_BIN / "pg_ctl"), "-D", str(PG_DATA), "status"], capture_output=True)
    if status.returncode:
        run(prefix + [PG_BIN / "pg_ctl", "-D", PG_DATA, "-l", PG_DATA / "server.log", "start", "-w"])
    import psycopg
    from psycopg import sql

    with psycopg.connect(
        host="127.0.0.1", port=PORT, dbname="postgres", user="boreal_admin", password=conf["admin"], autocommit=True
    ) as conn:
        for role, key in [("boreal_migration", "migration"), ("boreal_app", "runtime")]:
            if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone():
                conn.execute(
                    sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(role), sql.Literal(conf[key]))
                )
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname='boreal'").fetchone():
            conn.execute("CREATE DATABASE boreal OWNER boreal_migration")
    with psycopg.connect(
        host="127.0.0.1", port=PORT, dbname="boreal", user="boreal_admin", password=conf["admin"], autocommit=True
    ) as conn:
        conn.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
    print("Isolated PostgreSQL ready on loopback port 55432.")


def start():
    prepare()
    env = environment()
    run([sys.executable, "engine/build.py"], cwd=ROOT, env=env)
    run([sys.executable, "-m", "boreal.manage", "migrate"], cwd=ROOT, env=env)
    run([sys.executable, "-m", "boreal.manage", "bootstrap", "--output", ".local/accounts.json"], cwd=ROOT, env=env)
    runtime_env = dict(env)
    runtime_env.pop("BOREAL_MIGRATION_URL", None)
    pids = {}
    for name, command in [
        ("api", ["-m", "uvicorn", "boreal.api:app", "--host", "127.0.0.1", "--port", "8000"]),
        ("worker", ["scripts/supervise_worker.py"]),
    ]:
        pidfile = LOCAL / f"{name}.pid"
        if pidfile.exists():
            try:
                os.kill(int(pidfile.read_text()), 0)
                continue
            except (ProcessLookupError, ValueError):
                pass
        logfile = (LOCAL / f"{name}.log").open("ab")
        proc = subprocess.Popen(
            [sys.executable, *command],
            cwd=ROOT,
            env=runtime_env,
            stdout=logfile,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        pidfile.write_text(str(proc.pid))
        pids[name] = proc.pid
    import urllib.request
    import urllib.error

    for _ in range(60):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/api/health/live", timeout=2):
                break
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(1)
    else:
        raise SystemExit("API did not start. Inspect .local/api.log.")
    run([sys.executable, "scripts/seed.py"], cwd=ROOT, env=env)
    print("BOREAL is running at http://127.0.0.1:8000. Credentials: .local/accounts.json")


def stop():
    for name, expected in [("worker", "scripts/supervise_worker.py"), ("api", "boreal.api:app")]:
        pidfile = LOCAL / f"{name}.pid"
        if not pidfile.exists():
            continue
        pid = int(pidfile.read_text())
        cmdline = Path(f"/proc/{pid}/cmdline")
        if cmdline.exists() and expected in cmdline.read_bytes().decode(errors="replace"):
            os.kill(pid, signal.SIGTERM)
            for _ in range(50):
                if not cmdline.exists() or not cmdline.read_bytes():
                    break
                time.sleep(0.1)
        pidfile.unlink()
    print("BOREAL API and worker stopped; isolated database retained.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--exec", dest="command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.stop:
        stop()
    elif args.prepare:
        prepare()
    elif args.command:
        run(args.command, env=environment(), cwd=ROOT)
    else:
        start()
