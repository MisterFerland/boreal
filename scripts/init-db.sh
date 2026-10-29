#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v runtime_password="$BOREAL_RUNTIME_PASSWORD" -v migration_password="$BOREAL_MIGRATION_PASSWORD" <<'SQL'
CREATE ROLE boreal_migration LOGIN PASSWORD :'migration_password';
CREATE ROLE boreal_app LOGIN PASSWORD :'runtime_password';
ALTER DATABASE boreal OWNER TO boreal_migration;
GRANT ALL ON SCHEMA public TO boreal_migration;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
SQL
