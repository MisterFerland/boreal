"""Durable PostgreSQL worker with expiring, fenced claims and atomic chunk receipts.

Run separately from HTTP: python -m boreal.worker. Demonstration interruptions
exit this process. A supervisor/new worker recovers the expired durable claim.
"""

import argparse
import csv
import io
import json
import logging
import os
import re
import signal
import threading

from . import engine
from .common import audit, digest, financial_records, jsonb, new_id, proposals
from .db import connect
from .service import beneficiary_metadata, verify_snapshot

LEASE_SECONDS = max(3, int(os.environ.get("BOREAL_LEASE_SECONDS", "60")))
CHUNK_SIZE = min(500, max(1, int(os.environ.get("BOREAL_CHUNK_SIZE", "100"))))
OWNER = f"worker-{os.getpid()}-{new_id()[:8]}"
STOP = threading.Event()
LOG = logging.getLogger("boreal.worker")


class ClaimLost(RuntimeError):
    pass


def heartbeat(conn):
    conn.execute(
        """INSERT INTO worker_health(id) VALUES (%s)
        ON CONFLICT(id) DO UPDATE SET seen_at=now()""",
        (OWNER,),
    )


def claim():
    with connect() as conn:
        heartbeat(conn)
        row = conn.execute("""SELECT * FROM jobs WHERE
         (status IN ('queued','retry') OR (status='running' AND lease_until<now()))
         AND attempt_count<max_attempts ORDER BY created_at,id FOR UPDATE SKIP LOCKED LIMIT 1""").fetchone()
        if not row:
            # An abandoned final attempt becomes visibly terminal, not stuck forever.
            exhausted = conn.execute("""UPDATE jobs SET status='failed',error='RETRY_LIMIT: last worker claim expired',updated_at=now()
              WHERE status='running' AND lease_until<now() AND attempt_count>=max_attempts RETURNING id,batch_id,kind,payload""").fetchall()
            for item in exhausted:
                conn.execute(
                    "UPDATE attempts SET outcome='abandoned',finished_at=now(),error='Retry budget exhausted after claim expiry' WHERE job_id=%s AND outcome='running'",
                    (item["id"],),
                )
                if item["kind"] == "calculate":
                    conn.execute(
                        "UPDATE batches SET status='failed',errors=%s WHERE id=%s AND status='calculating'",
                        (jsonb(["RETRY_LIMIT: last worker claim expired"]), item["batch_id"]),
                    )
                if item["kind"] == "reconcile":
                    conn.execute(
                        "UPDATE settlement_imports SET status='failed' WHERE id=%s", (item["payload"]["import_id"],)
                    )
                audit(conn, OWNER, "job.exhausted", item["id"])
            return None
        conn.execute(
            "UPDATE attempts SET outcome='abandoned',finished_at=now(),error='Claim expired; fenced by recovery' WHERE job_id=%s AND outcome='running'",
            (row["id"],),
        )
        row = conn.execute(
            """UPDATE jobs SET status='running',owner=%s,fence=fence+1,attempt_count=attempt_count+1,
          lease_until=now()+make_interval(secs=>%s),updated_at=now(),error=NULL WHERE id=%s RETURNING *""",
            (OWNER, LEASE_SECONDS, row["id"]),
        ).fetchone()
        conn.execute("INSERT INTO attempts(job_id,fence,owner) VALUES (%s,%s,%s)", (row["id"], row["fence"], OWNER))
        audit(conn, OWNER, "job.claimed", row["id"], {"fence": row["fence"], "attempt": row["attempt_count"]})
        return row


def assert_claim(conn, job):
    row = conn.execute("SELECT *,lease_until>now() AS live FROM jobs WHERE id=%s FOR UPDATE", (job["id"],)).fetchone()
    if (
        not row
        or row["status"] != "running"
        or row["owner"] != OWNER
        or row["fence"] != job["fence"]
        or not row["live"]
    ):
        raise ClaimLost("Worker no longer owns a live fenced claim")
    return row


class LeaseKeeper:
    def __init__(self, job):
        self.job = job
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join(timeout=2)

    def run(self):
        while not self.stop.wait(max(0.5, LEASE_SECONDS / 4)):
            try:
                with connect() as conn:
                    heartbeat(conn)
                    row = conn.execute(
                        """UPDATE jobs SET lease_until=now()+make_interval(secs=>%s)
                     WHERE id=%s AND owner=%s AND fence=%s AND status='running' AND lease_until>now() RETURNING id""",
                        (LEASE_SECONDS, self.job["id"], OWNER, self.job["fence"]),
                    ).fetchone()
                    if not row:
                        return
            except Exception:
                LOG.exception("lease_renewal_failed")
                return


def finish(conn, job, result=None):
    assert_claim(conn, job)
    conn.execute(
        "UPDATE jobs SET status='succeeded',completed=total,result=%s,lease_until=NULL,updated_at=now() WHERE id=%s",
        (jsonb(result or {}), job["id"]),
    )
    conn.execute(
        "UPDATE attempts SET outcome='succeeded',finished_at=now() WHERE job_id=%s AND fence=%s",
        (job["id"], job["fence"]),
    )
    audit(conn, OWNER, "job.completed", job["id"], {"kind": job["kind"]})


def apply_reference_snapshot(records, snapshot):
    conflicts = set(snapshot.get("conflicting_positions", []))
    for row in records:
        names = snapshot.get("beneficiaries", {}).get(row.get("beneficiary"))
        if names:
            row["beneficiary_names"] = names
        if row["position"] in conflicts:
            row.update(reason="BUSINESS_KEY_CONFLICT", payable=None, proposal=None)
    return records


def calculate_frozen(batch, policy, build_id=None):
    raw = batch["raw"]
    if batch["schema_version"] == "BOREAL-MIXED01":
        try:
            decoded = engine.decode_mixed(raw, build_id=build_id)
        except engine.EngineError as exc:
            if str(exc).startswith(("MIXED_", "PACKED_")):
                return {
                    "status": "quarantined",
                    "count": 0,
                    "errors": [str(exc)],
                    "records": [],
                    "engine_build": engine.build_info(build_id)["engine_build"],
                }
            raise
        result = engine.calculate(decoded, policy, build_id=build_id)
        for row in result["records"]:
            start = 81 + (row["position"] - 2) * 74
            row["raw_hex"] = raw[start : start + 73].hex()
            row["legacy_format"] = "BOREAL-MIXED01"
        return result
    return engine.calculate(raw, policy, build_id=build_id)


def calculate_job(job):
    with connect() as conn:
        assert_claim(conn, job)
        batch = conn.execute("SELECT * FROM batches WHERE id=%s FOR UPDATE", (job["batch_id"],)).fetchone()
        conn.execute(
            "UPDATE batches SET status='calculating' WHERE id=%s AND status IN ('queued','failed')", (batch["id"],)
        )
    result = calculate_frozen(batch, batch["policy"])
    with connect() as conn:
        assert_claim(conn, job)
        if result["status"] == "quarantined":
            conn.execute(
                "UPDATE batches SET status='quarantined',errors=%s,record_count=%s,engine_build=%s WHERE id=%s",
                (jsonb(result.get("errors", [])), result.get("count", 0), result["engine_build"], batch["id"]),
            )
            audit(conn, OWNER, "batch.quarantined", batch["id"], {"errors": result.get("errors", [])})
            finish(conn, job, {"status": "quarantined", "errors": result.get("errors", [])})
            return
        existing = {
            (r["source"], r["reference"])
            for r in conn.execute("SELECT source,reference FROM journals WHERE kind='obligation'")
        }
        conflicts = [
            r["position"]
            for r in result["records"]
            if r["reason"] == "ACCEPTED" and (r["source"], r["reference"]) in existing
        ]
        snapshot = {
            "conflicting_positions": conflicts,
            "program": "CIR1",
            "currency": "CAD",
            "policy": batch["policy"],
            "beneficiaries": beneficiary_metadata(),
        }
        records = apply_reference_snapshot(result["records"], snapshot)
        values = []
        for r in records:
            amount = r.get("eligible_cost")
            # Invalid external numeric representations never enter NUMERIC storage.
            if amount is not None and not re.fullmatch(r"-?\d{1,7}\.\d{2}", str(amount)):
                amount = None
            values.append(
                (
                    new_id(),
                    batch["id"],
                    r["position"],
                    r["source"],
                    r["reference"],
                    r["reason"],
                    amount,
                    r.get("payable"),
                    "accepted" if r["reason"] == "ACCEPTED" else "rejected",
                    jsonb(r),
                )
            )
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO records(id,batch_id,position,source,reference,reason,eligible_cost,payable,state,data)
                              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                values,
            )
        totals = conn.execute(
            """SELECT count(*) FILTER(WHERE state='accepted') AS accepted,
         count(*) FILTER(WHERE state='rejected') AS rejected,coalesce(sum(payable),0)::numeric(16,2) AS total
         FROM records WHERE batch_id=%s""",
            (batch["id"],),
        ).fetchone()
        result_digest = digest(financial_records(records))
        conn.execute(
            """UPDATE batches SET status='review',record_count=%s,accepted_count=%s,rejected_count=%s,
          control_total=%s,payable_total=%s,result_digest=%s,proposal_digest=%s,engine_build=%s,reference_snapshot=%s,errors=%s WHERE id=%s""",
            (
                len(records),
                totals["accepted"],
                totals["rejected"],
                result["control_total"],
                totals["total"],
                result_digest,
                digest(proposals(records)),
                result["engine_build"],
                jsonb(snapshot),
                jsonb(result.get("errors", [])),
                batch["id"],
            ),
        )
        conn.execute("UPDATE jobs SET total=%s WHERE id=%s", (len(records), job["id"]))
        audit(
            conn,
            OWNER,
            "batch.calculated",
            batch["id"],
            {
                "accepted": totals["accepted"],
                "rejected": totals["rejected"],
                "result_digest": result_digest,
                "engine_build": result["engine_build"],
            },
        )
        finish(conn, job, {"status": "review", "result_digest": result_digest})


def post_job(job):
    with connect() as conn:
        assert_claim(conn, job)
        batch = conn.execute("SELECT * FROM batches WHERE id=%s", (job["batch_id"],)).fetchone()
        verify_snapshot(conn, batch)
        approval = conn.execute("SELECT * FROM approvals WHERE batch_id=%s", (batch["id"],)).fetchone()
        if not approval or any(
            approval[k] != batch[k]
            for k in ("source_sha256", "result_digest", "proposal_digest", "policy", "engine_build")
        ):
            raise RuntimeError("APPROVAL_INVALID: frozen proposal binding differs")
        records = conn.execute(
            "SELECT id FROM records WHERE batch_id=%s AND reason='ACCEPTED' ORDER BY source,reference,position",
            (batch["id"],),
        ).fetchall()
    ids = [r["id"] for r in records]
    for chunk, start in enumerate(range(0, len(ids), CHUNK_SIZE)):
        selected = ids[start : start + CHUNK_SIZE]
        injection = None
        with connect() as conn:
            current = assert_claim(conn, job)
            if conn.execute("SELECT 1 FROM receipts WHERE job_id=%s AND chunk=%s", (job["id"], chunk)).fetchone():
                continue
            if current["failure_mode"] and not current["failure_injected"]:
                if os.environ.get("BOREAL_DEMO") != "1":
                    raise RuntimeError("DEMO_CONTROL_DISABLED: failure request outside local demo profile")
                injection = current["failure_mode"]
                conn.execute("UPDATE jobs SET failure_injected=true WHERE id=%s", (job["id"],))
                audit(conn, OWNER, "demo.interruption_armed", job["id"], {"mode": injection, "chunk": chunk})
        with connect() as conn:
            assert_claim(conn, job)
            locked = conn.execute(
                "SELECT * FROM records WHERE id=ANY(%s) ORDER BY source,reference,position FOR UPDATE", (selected,)
            ).fetchall()
            for record in locked:
                if record["state"] != "accepted":
                    raise RuntimeError("RECORD_STATE_CONFLICT: expected an unposted approved record")
            # psycopg executemany pipelines this bounded chunk, avoiding two
            # client round trips per record. The same DB constraints still run
            # for every journal, and all effects remain in this transaction.
            with conn.cursor() as cur:
                cur.executemany(
                    """INSERT INTO journals(id,kind,batch_id,record_id,source,reference,amount,debit,credit,actor)
                  VALUES (%s,'obligation',%s,%s,%s,%s,%s,%s,%s,%s)""",
                    [
                        (
                            new_id(),
                            r["batch_id"],
                            r["id"],
                            r["source"],
                            r["reference"],
                            r["data"]["proposal"]["amount"],
                            r["data"]["proposal"]["debit"],
                            r["data"]["proposal"]["credit"],
                            job["submitted_by"],
                        )
                        for r in locked
                    ],
                )
            conn.execute("UPDATE records SET state='posted' WHERE id=ANY(%s)", (selected,))
            conn.execute(
                "INSERT INTO receipts(job_id,chunk,record_ids,digest) VALUES (%s,%s,%s,%s)",
                (job["id"], chunk, jsonb(selected), digest([r["data"]["proposal"] for r in locked])),
            )
            conn.execute(
                "UPDATE jobs SET completed=completed+%s,updated_at=now() WHERE id=%s", (len(locked), job["id"])
            )
            audit(conn, OWNER, "posting.chunk_committed", job["id"], {"chunk": chunk, "records": len(locked)})
            if injection == "before_commit":
                os._exit(86)  # Real process termination: PostgreSQL rolls back the open transaction.
        if injection == "after_commit":
            os._exit(87)  # Receipt and financial effects exist; completion acknowledgement does not.
    with connect() as conn:
        assert_claim(conn, job)
        remaining = conn.execute(
            "SELECT count(*) AS n FROM records WHERE batch_id=%s AND reason='ACCEPTED' AND state='accepted'",
            (batch["id"],),
        ).fetchone()["n"]
        if remaining:
            raise RuntimeError("POSTING_INCOMPLETE: accepted records remain without receipts")
        conn.execute("UPDATE batches SET status='posted' WHERE id=%s", (batch["id"],))
        finish(
            conn,
            job,
            {
                "posted_records": len(ids),
                "guarantee": "One committed financial effect per business key despite retries.",
            },
        )


def inspect_job(job):
    with connect() as conn:
        assert_claim(conn, job)
        batch = conn.execute("SELECT * FROM batches WHERE id=%s", (job["batch_id"],)).fetchone()
        old = [
            r["data"]
            for r in conn.execute("SELECT data FROM records WHERE batch_id=%s ORDER BY position", (batch["id"],))
        ]
    policy = "V2" if job["kind"] == "compare" else batch["policy"]
    replay = calculate_frozen(batch, policy, build_id=batch["engine_build"])
    if replay["status"] != "verified":
        raise RuntimeError("REPLAY_VALIDATION_FAILED: frozen input did not verify")
    new = apply_reference_snapshot(replay["records"], batch["reference_snapshot"])
    old_fin, new_fin = financial_records(old), financial_records(new)
    differences = [
        {"position": a["position"], "before": a, "after": b} for a, b in zip(old_fin, new_fin, strict=True) if a != b
    ]
    old_values = [r["payable"] for r in old if r.get("payable")]
    new_values = [r["payable"] for r in new if r.get("payable")]
    old_total = engine.aggregate(old_values, build_id=batch["engine_build"])
    new_total = engine.aggregate(new_values, build_id=batch["engine_build"])
    delta = engine.aggregate(new_values + ["-" + value for value in old_values], build_id=batch["engine_build"])
    result = {
        "same": digest(old_fin) == digest(new_fin),
        "original_digest": batch["result_digest"],
        "replay_digest": digest(new_fin),
        "differences": differences,
        "difference_count": len(differences),
        "v1_total": old_total,
        "v2_total": new_total,
        "delta": delta,
        "engine_build": batch["engine_build"],
        "policy": policy,
        "side_effects": "No business or journal mutations; job and audit evidence only.",
    }
    with connect() as conn:
        finish(conn, job, result)


def reconcile_job(job):
    with connect() as conn:
        assert_claim(conn, job)
        imported = conn.execute(
            "SELECT * FROM settlement_imports WHERE id=%s", (job["payload"]["import_id"],)
        ).fetchone()
        obligations = conn.execute(
            "SELECT * FROM records WHERE state IN ('posted','settled') ORDER BY source,reference"
        ).fetchall()
        settled_refs = {
            r["settlement_reference"]
            for r in conn.execute("SELECT settlement_reference FROM journals WHERE kind='settlement'")
        }
    try:
        text = imported["raw"].decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("SETTLEMENT_ENCODING: expected UTF-8 CSV") from exc
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames != ["settlement_reference", "source", "reference", "amount"]:
        raise ValueError("SETTLEMENT_COLUMNS: expected settlement_reference,source,reference,amount")
    expected = {(r["source"], r["reference"]): r for r in obligations}
    rows = []
    seen_refs = set()
    seen_business = set()
    for position, row in enumerate(reader, 1):
        if position > 100000:
            raise ValueError("SETTLEMENT_LIMIT: maximum 100000 rows")
        if None in row or any(v is None for v in row.values()) or not re.fullmatch(r"\d{1,7}\.\d{2}", row["amount"]):
            raise ValueError(f"SETTLEMENT_SYNTAX: malformed row {position}")
        if any(
            not re.fullmatch(r"[A-Za-z0-9_-]{1," + str(limit) + "}", row[key])
            for key, limit in [("source", 8), ("reference", 20), ("settlement_reference", 32)]
        ):
            raise ValueError(f"SETTLEMENT_REFERENCE: invalid row {position}")
        identity = (row["source"], row["reference"])
        record = expected.get(identity)
        duplicate = (
            row["settlement_reference"] in seen_refs
            or row["settlement_reference"] in settled_refs
            or identity in seen_business
            or (record is not None and record["state"] == "settled")
        )
        seen_refs.add(row["settlement_reference"])
        seen_business.add(identity)
        rows.append(
            {
                "position": position,
                "source": row["source"],
                "reference": row["reference"],
                "settlement_reference": row["settlement_reference"],
                "received": row["amount"],
                "expected": format(record["payable"], ".2f") if record else None,
                "duplicate": duplicate,
                "record_id": str(record["id"]) if record else None,
            }
        )
    for identity, record in expected.items():
        if identity not in seen_business and record["state"] == "posted":
            rows.append(
                {
                    "position": len(rows) + 1,
                    "source": identity[0],
                    "reference": identity[1],
                    "settlement_reference": None,
                    "received": None,
                    "expected": format(record["payable"], ".2f"),
                    "duplicate": False,
                    "record_id": str(record["id"]),
                }
            )
    classified = engine.reconcile(rows)
    with connect() as conn:
        assert_claim(conn, job)
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO reconciliations(id,import_id,position,source,reference,settlement_reference,record_id,expected,received,classification,data)
              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                [
                    (
                        new_id(),
                        imported["id"],
                        r["position"],
                        r["source"],
                        r["reference"],
                        r.get("settlement_reference"),
                        r.get("record_id"),
                        r.get("expected"),
                        r.get("received"),
                        r["classification"],
                        jsonb(r),
                    )
                    for r in classified
                ],
            )
        conn.execute("UPDATE settlement_imports SET status='review' WHERE id=%s", (imported["id"],))
        conn.execute("UPDATE jobs SET total=%s WHERE id=%s", (len(classified), job["id"]))
        audit(conn, OWNER, "settlement.classified", imported["id"], {"rows": len(classified)})
        finish(conn, job, {"import_id": str(imported["id"]), "rows": len(classified)})


def run_one():
    job = claim()
    if not job:
        return False
    LOG.info(json.dumps({"event": "job_started", "job_id": str(job["id"]), "kind": job["kind"], "fence": job["fence"]}))
    try:
        with LeaseKeeper(job):
            {
                "calculate": calculate_job,
                "post": post_job,
                "replay": inspect_job,
                "compare": inspect_job,
                "reconcile": reconcile_job,
            }[job["kind"]](job)
    except ClaimLost:
        LOG.warning(json.dumps({"event": "claim_lost", "job_id": str(job["id"])}))
    except Exception as exc:
        LOG.exception("job_failed %s", job["id"])
        error = f"{type(exc).__name__}: {str(exc)[:1000]}"
        try:
            with connect() as conn:
                current = assert_claim(conn, job)
                status = "failed" if current["attempt_count"] >= current["max_attempts"] else "retry"
                conn.execute(
                    "UPDATE jobs SET status=%s,error=%s,lease_until=NULL,updated_at=now() WHERE id=%s",
                    (status, error, job["id"]),
                )
                conn.execute(
                    "UPDATE attempts SET outcome='failed',error=%s,finished_at=now() WHERE job_id=%s AND fence=%s",
                    (error, job["id"], job["fence"]),
                )
                if status == "failed" and job["kind"] == "calculate":
                    conn.execute(
                        "UPDATE batches SET status='failed',errors=%s WHERE id=%s AND status='calculating'",
                        (jsonb([error]), job["batch_id"]),
                    )
                if status == "failed" and job["kind"] == "reconcile":
                    conn.execute(
                        "UPDATE settlement_imports SET status='failed' WHERE id=%s", (job["payload"]["import_id"],)
                    )
                audit(conn, OWNER, "job.attempt_failed", job["id"], {"error": error, "status": status})
        except ClaimLost:
            pass
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Claim at most one durable job")
    parser.add_argument("--drain", action="store_true", help="Exit when no work is immediately claimable")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    signal.signal(signal.SIGTERM, lambda *_: STOP.set())
    signal.signal(signal.SIGINT, lambda *_: STOP.set())
    while not STOP.is_set():
        worked = run_one()
        if args.once or (args.drain and not worked):
            break
        if not worked:
            STOP.wait(1)


if __name__ == "__main__":
    main()
