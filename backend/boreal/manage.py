"""Migration/bootstrap commands use a separate privileged migration identity."""

import argparse
import json
import os
import secrets
from pathlib import Path

from psycopg import sql

from .auth import PASSWORD_HASHER
from .common import audit
from .db import connect

ROOT = Path(__file__).resolve().parents[2]


def migrate():
    with connect(migration=True) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(714020260)")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations(version text PRIMARY KEY,applied_at timestamptz NOT NULL DEFAULT now())"
        )
        existing = {r["version"] for r in conn.execute("SELECT version FROM schema_migrations")}
        for path in sorted((ROOT / "migrations").glob("*.sql")):
            if path.name.split("_")[0] not in existing:
                conn.execute(path.read_text(encoding="utf-8"))
                print(f"Applied {path.name}")
        role = os.environ.get("BOREAL_APP_ROLE", "boreal_app")
        if conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone():
            conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
            conn.execute(
                sql.SQL("GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO {}").format(
                    sql.Identifier(role)
                )
            )
            conn.execute(
                sql.SQL("GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(sql.Identifier(role))
            )
            conn.execute(sql.SQL("REVOKE ALL ON schema_migrations FROM {}").format(sql.Identifier(role)))
            conn.execute(sql.SQL("REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON users FROM {}").format(sql.Identifier(role)))
            for table in ("journals", "audit", "approvals", "receipts"):
                conn.execute(
                    sql.SQL("REVOKE UPDATE,DELETE,TRUNCATE ON {} FROM {}").format(
                        sql.Identifier(table), sql.Identifier(role)
                    )
                )
            for table in ("records", "batches", "settlement_imports", "reconciliations", "attempts"):
                conn.execute(
                    sql.SQL("REVOKE DELETE,TRUNCATE ON {} FROM {}").format(sql.Identifier(table), sql.Identifier(role))
                )
            conn.execute(sql.SQL("REVOKE CREATE ON SCHEMA public FROM {}").format(sql.Identifier(role)))
        conn.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")


def bootstrap(output):
    target = Path(output)
    if target.exists():
        print(f"Credential file already exists: {target}. Existing credentials retained.")
        return
    accounts = []
    with connect(migration=True) as conn:
        for role in ("operator", "approver", "auditor"):
            if conn.execute("SELECT 1 FROM users WHERE id=%s", (role,)).fetchone():
                raise RuntimeError(
                    "Accounts already exist but credential file is missing. Use explicit password reset; refusing to overwrite users."
                )
            password = secrets.token_urlsafe(24)
            conn.execute(
                "INSERT INTO users(id,username,role,password_hash) VALUES (%s,%s,%s,%s)",
                (role, role, role, PASSWORD_HASHER.hash(password)),
            )
            accounts.append({"username": role, "role": role, "password": password})
        audit(conn, "bootstrap", "accounts.created", "local-demo", {"roles": ["operator", "approver", "auditor"]})
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        json.dump({"accounts": accounts}, out, indent=2)
    print(f"Generated credentials saved privately to {target}. Passwords are not written to logs.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate")
    boot = sub.add_parser("bootstrap")
    boot.add_argument("--output", default=".local/accounts.json")
    args = parser.parse_args()
    if args.command == "migrate":
        migrate()
    else:
        bootstrap(args.output)


if __name__ == "__main__":
    main()
