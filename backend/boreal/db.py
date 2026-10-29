"""Short, explicit PostgreSQL transactions. No embedded database fallback."""

import os
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row


@contextmanager
def connect(*, migration=False):
    key = "BOREAL_MIGRATION_URL" if migration else "BOREAL_DATABASE_URL"
    url = os.environ.get(key) or (os.environ.get("BOREAL_DATABASE_URL") if migration else None)
    if not url:
        raise RuntimeError(f"{key} is required")
    with psycopg.connect(url, row_factory=dict_row, connect_timeout=10) as connection:
        yield connection
