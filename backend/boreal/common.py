"""Canonical data, identities and ordered audit chain."""

import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from psycopg.types.json import Jsonb


def serialize(value):
    if isinstance(value, Decimal):
        return format(value, ".2f")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    raise TypeError(type(value).__name__)


def canonical(value):
    return json.dumps(value, default=serialize, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def clean(value):
    return json.loads(canonical(value))


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def new_id():
    return str(uuid.uuid4())


def jsonb(value):
    return Jsonb(clean(value))


def audit(conn, actor, action, subject, details=None):
    # All appending transactions take the same lock, assigning one concurrency order.
    conn.execute("SELECT pg_advisory_xact_lock(714020261)")
    last = conn.execute("SELECT hash FROM audit ORDER BY sequence DESC LIMIT 1").fetchone()
    previous = last["hash"] if last else "0" * 64
    event = {
        "actor": actor,
        "action": action,
        "subject": str(subject),
        "details": details or {},
        "at": datetime.now(timezone.utc).isoformat(),
    }
    current = hashlib.sha256((previous + "\n" + canonical(event)).encode()).hexdigest()
    conn.execute("INSERT INTO audit(event,previous_hash,hash) VALUES (%s,%s,%s)", (jsonb(event), previous, current))


def verify_audit(conn):
    previous = "0" * 64
    count = 0
    for row in conn.execute("SELECT * FROM audit ORDER BY sequence"):
        expected = hashlib.sha256((previous + "\n" + canonical(row["event"])).encode()).hexdigest()
        if row["previous_hash"] != previous or row["hash"] != expected:
            return {"valid": False, "count": count, "head": previous, "broken_sequence": row["sequence"]}
        previous = row["hash"]
        count += 1
    return {
        "valid": True,
        "count": count,
        "head": previous,
        "limitation": "A privileged rewrite of the complete chain and its trusted anchor is outside this local model.",
    }


def financial_records(records):
    """No operational state, timestamps, IDs or attempts enter a financial digest."""
    keys = (
        "position",
        "source",
        "reference",
        "program",
        "business_date",
        "eligible_cost",
        "beneficiary",
        "reason",
        "payable",
        "trace",
        "proposal",
        "raw_hex",
    )
    return [{key: row.get(key) for key in keys} for row in sorted(records, key=lambda r: r["position"])]


def proposals(records):
    return [
        {"position": r["position"], "source": r["source"], "reference": r["reference"], "proposal": r["proposal"]}
        for r in sorted(records, key=lambda r: r["position"])
        if r.get("proposal")
    ]
