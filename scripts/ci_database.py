"""Initialize only the explicitly configured ephemeral CI roles; passwords remain in environment."""

import os
from urllib.parse import urlsplit
import psycopg
from psycopg import sql

admin = os.environ["BOREAL_TEST_ADMIN_URL"]
with psycopg.connect(admin, autocommit=True) as conn:
    for variable in ("BOREAL_MIGRATION_URL", "BOREAL_DATABASE_URL"):
        parsed = urlsplit(os.environ[variable])
        if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (parsed.username,)).fetchone():
            conn.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(parsed.username), sql.Literal(parsed.password)
                )
            )
    migration = urlsplit(os.environ["BOREAL_MIGRATION_URL"])
    conn.execute(
        sql.SQL("ALTER DATABASE {} OWNER TO {}").format(
            sql.Identifier(migration.path.lstrip("/")), sql.Identifier(migration.username)
        )
    )
