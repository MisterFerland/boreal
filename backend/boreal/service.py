"""Transport-independent commands; each command commits one atomic transaction."""

import hashlib
import json
import os
import re
from functools import lru_cache
from pathlib import Path

from . import engine
from .auth import fail, require
from .common import audit, clean, digest, financial_records, jsonb, new_id, proposals

MAX_UPLOAD = 12 * 1024 * 1024


@lru_cache(maxsize=1)
def beneficiary_metadata():
    path = Path(__file__).resolve().parents[2] / "fixtures" / "beneficiaries.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def batch_view(row):
    if not row:
        fail("BATCH_NOT_FOUND", "Batch not found.", 404)
    return clean({k: v for k, v in row.items() if k not in ("raw",)})


def record_view(row):
    result = dict(row["data"])
    result.update({k: row[k] for k in ("id", "batch_id", "state")})
    names = result.get("beneficiary_names") or beneficiary_metadata().get(result.get("beneficiary"))
    if names:
        result["beneficiary_names"] = names
    return clean(result)


def job_view(conn, job):
    if not job:
        fail("JOB_NOT_FOUND", "Job not found.", 404)
    result = clean(job)
    result["attempts"] = clean(
        conn.execute("SELECT * FROM attempts WHERE job_id=%s ORDER BY fence", (job["id"],)).fetchall()
    )
    for attempt in result["attempts"]:
        attempt.update(attempt=attempt["fence"], status=attempt["outcome"])
    if result.get("result") and isinstance(result["result"].get("differences"), list):
        result["result"]["differences"] = result["result"]["differences"][:100]
        result["result"]["differences_url"] = f"/api/jobs/{job['id']}/differences"
    return result


def audit_view(row):
    result = clean(row)
    result.update(
        id=str(row["sequence"]),
        action=row["event"]["action"],
        actor=row["event"]["actor"],
        subject=row["event"]["subject"],
        created_at=row["event"]["at"],
    )
    return result


def idempotent(conn, actor, key, payload, operation):
    if not key or not re.fullmatch(r"[A-Za-z0-9_.:-]{8,128}", key):
        fail("IDEMPOTENCY_REQUIRED", "An Idempotency-Key of 8–128 safe characters is required.", 400)
    conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (actor + ":" + key,))
    old = conn.execute("SELECT * FROM idempotency WHERE actor=%s AND key=%s", (actor, key)).fetchone()
    fingerprint = digest(payload)
    if old:
        if old["payload_digest"] != fingerprint:
            fail("IDEMPOTENCY_CONFLICT", "This request key was already used with different content.", 409)
        return old["response"]
    result = clean(operation())
    conn.execute(
        "INSERT INTO idempotency(actor,key,payload_digest,response) VALUES (%s,%s,%s,%s)",
        (actor, key, fingerprint, jsonb(result)),
    )
    return result


def create_job(conn, actor, kind, batch_id=None, payload=None, total=0, failure_mode=None):
    job_id = new_id()
    row = conn.execute(
        """INSERT INTO jobs(id,batch_id,kind,status,submitted_by,payload,total,failure_mode)
        VALUES (%s,%s,%s,'queued',%s,%s,%s,%s) RETURNING *""",
        (job_id, batch_id, kind, actor, jsonb(payload or {}), total, failure_mode),
    ).fetchone()
    audit(conn, actor, "job.submitted", job_id, {"kind": kind, "batch_id": str(batch_id) if batch_id else None})
    return job_view(conn, row)


def import_batch(conn, user, key, name, raw):
    require(user, "operator")
    if not raw or len(raw) > MAX_UPLOAD:
        fail("UPLOAD_SIZE", "The import must contain 1 byte to 12 MiB.", 413)
    sha = hashlib.sha256(raw).hexdigest()

    def operation():
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("file:" + sha,))
        old = conn.execute("SELECT * FROM batches WHERE source_sha256=%s", (sha,)).fetchone()
        if old:
            return batch_view(old)
        batch_id = new_id()
        schema = "BOREAL-MIXED01" if name.lower().endswith(".bin") else "BOREAL01"
        conn.execute(
            "INSERT INTO batches(id,name,status,raw,source_sha256,submitted_by,schema_version) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (batch_id, name[:160], "queued", raw, sha, user["id"], schema),
        )
        job = create_job(conn, user["id"], "calculate", batch_id)
        conn.execute("UPDATE batches SET job_id=%s WHERE id=%s", (job["id"], batch_id))
        audit(conn, user["id"], "batch.imported", batch_id, {"sha256": sha, "bytes": len(raw), "filename": name[:160]})
        return batch_view(conn.execute("SELECT * FROM batches WHERE id=%s", (batch_id,)).fetchone())

    return idempotent(conn, user["id"], key, {"op": "import", "sha256": sha}, operation)


def verify_snapshot(conn, batch):
    records = [
        r["data"] for r in conn.execute("SELECT data FROM records WHERE batch_id=%s ORDER BY position", (batch["id"],))
    ]
    if (
        hashlib.sha256(batch["raw"]).hexdigest() != batch["source_sha256"]
        or digest(financial_records(records)) != batch["result_digest"]
        or digest(proposals(records)) != batch["proposal_digest"]
    ):
        fail("SNAPSHOT_INVALID", "Frozen calculation or journal proposals failed integrity verification.", 409)
    return records


def approve(conn, user, key, batch_id):
    require(user, "approver")

    def operation():
        batch = conn.execute("SELECT * FROM batches WHERE id=%s FOR UPDATE", (batch_id,)).fetchone()
        batch_view(batch)
        if batch["submitted_by"] == user["id"]:
            fail("SELF_APPROVAL", "The submitting actor cannot approve this batch.", 403)
        if batch["status"] != "review" or batch["accepted_count"] == 0:
            fail("NOT_REVIEWABLE", "Only a reviewed batch with accepted records can be approved.", 409)
        verify_snapshot(conn, batch)
        conn.execute(
            """INSERT INTO approvals(batch_id,approved_by,source_sha256,result_digest,proposal_digest,policy,engine_build)
                     VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (
                batch_id,
                user["id"],
                batch["source_sha256"],
                batch["result_digest"],
                batch["proposal_digest"],
                batch["policy"],
                batch["engine_build"],
            ),
        )
        conn.execute("UPDATE batches SET status='approved' WHERE id=%s", (batch_id,))
        audit(
            conn,
            user["id"],
            "batch.approved",
            batch_id,
            {
                "accepted": batch["accepted_count"],
                "rejected": batch["rejected_count"],
                "result_digest": batch["result_digest"],
            },
        )
        batch["status"] = "approved"
        return batch_view(batch)

    return idempotent(conn, user["id"], key, {"op": "approve", "batch": str(batch_id)}, operation)


def post(conn, user, key, batch_id, failure_mode=None):
    require(user, "approver")
    if failure_mode and (os.environ.get("BOREAL_DEMO") != "1" or failure_mode not in ("before_commit", "after_commit")):
        fail("DEMO_CONTROL_DISABLED", "Interruption controls require the explicit local demonstration profile.", 403)

    def operation():
        batch = conn.execute("SELECT * FROM batches WHERE id=%s FOR UPDATE", (batch_id,)).fetchone()
        batch_view(batch)
        if batch["status"] != "approved":
            fail("NOT_APPROVED", "This batch is not awaiting posting.", 409)
        verify_snapshot(conn, batch)
        approval = conn.execute("SELECT * FROM approvals WHERE batch_id=%s", (batch_id,)).fetchone()
        if not approval or any(
            approval[k] != batch[k]
            for k in ("source_sha256", "result_digest", "proposal_digest", "policy", "engine_build")
        ):
            fail("APPROVAL_INVALID", "Approval does not match the frozen input and proposals.", 409)
        job = create_job(conn, user["id"], "post", batch_id, total=batch["accepted_count"], failure_mode=failure_mode)
        conn.execute("UPDATE batches SET status='posting',job_id=%s WHERE id=%s", (job["id"], batch_id))
        return job

    return idempotent(
        conn, user["id"], key, {"op": "post", "batch": str(batch_id), "failure_mode": failure_mode}, operation
    )


def queue_inspection(conn, user, key, batch_id, kind):
    def operation():
        batch = conn.execute("SELECT * FROM batches WHERE id=%s", (batch_id,)).fetchone()
        batch_view(batch)
        if not batch["result_digest"]:
            fail("NO_CALCULATION", "A completed calculation is required.", 409)
        return create_job(conn, user["id"], kind, batch_id, total=batch["record_count"])

    return idempotent(conn, user["id"], key, {"op": kind, "batch": str(batch_id)}, operation)


def retry_job(conn, user, key, job_id):
    def operation():
        job = conn.execute("SELECT * FROM jobs WHERE id=%s FOR UPDATE", (job_id,)).fetchone()
        if not job:
            fail("JOB_NOT_FOUND", "Job not found.", 404)
        allowed = (
            ("approver",)
            if job["kind"] == "post"
            else (("operator",) if job["kind"] in ("calculate", "reconcile") else ("operator", "approver", "auditor"))
        )
        require(user, *allowed)
        if job["status"] not in ("failed", "retry"):
            fail("NOT_RETRYABLE", "This job is not awaiting a retry.", 409)
        conn.execute(
            "UPDATE jobs SET status='queued',max_attempts=attempt_count+5,error=NULL,updated_at=now() WHERE id=%s",
            (job_id,),
        )
        audit(conn, user["id"], "job.retry_requested", job_id)
        return job_view(conn, conn.execute("SELECT * FROM jobs WHERE id=%s", (job_id,)).fetchone())

    return idempotent(conn, user["id"], key, {"op": "retry", "job": str(job_id)}, operation)


def reverse(conn, user, key, journal_id, reason):
    require(user, "approver")

    def operation():
        journal = conn.execute("SELECT * FROM journals WHERE id=%s", (journal_id,)).fetchone()
        if not journal:
            fail("JOURNAL_NOT_FOUND", "Journal not found.", 404)
        rec = conn.execute("SELECT * FROM records WHERE id=%s FOR UPDATE", (journal["record_id"],)).fetchone()
        if journal["kind"] != "obligation" or rec["state"] != "posted":
            fail("NOT_REVERSIBLE", "Only an unsettled, unreversed obligation can be reversed.", 409)
        batch = conn.execute("SELECT engine_build FROM batches WHERE id=%s", (rec["batch_id"],)).fetchone()
        proposal = engine.reverse(
            {"amount": format(journal["amount"], ".2f"), "debit": journal["debit"], "credit": journal["credit"]},
            build_id=batch["engine_build"],
        )
        new = insert_journal(conn, rec, "reversal", proposal, user["id"], reversal_of=journal_id, reason=reason)
        conn.execute("UPDATE records SET state='reversed' WHERE id=%s", (rec["id"],))
        audit(conn, user["id"], "journal.reversed", new["id"], {"original": str(journal_id), "reason": reason})
        return clean(new)

    return idempotent(conn, user["id"], key, {"op": "reverse", "journal": str(journal_id), "reason": reason}, operation)


def insert_journal(conn, record, kind, proposal, actor, *, reversal_of=None, settlement_reference=None, reason=None):
    return conn.execute(
        """INSERT INTO journals(id,kind,batch_id,record_id,source,reference,amount,debit,credit,actor,reversal_of,settlement_reference,reason)
      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
        (
            new_id(),
            kind,
            record["batch_id"],
            record["id"],
            record["source"],
            record["reference"],
            proposal["amount"],
            proposal["debit"],
            proposal["credit"],
            actor,
            reversal_of,
            settlement_reference,
            reason,
        ),
    ).fetchone()


def import_settlement(conn, user, key, name, raw):
    require(user, "operator")
    if not raw or len(raw) > MAX_UPLOAD:
        fail("UPLOAD_SIZE", "The import must contain 1 byte to 12 MiB.", 413)
    sha = hashlib.sha256(raw).hexdigest()

    def operation():
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("settlement:" + sha,))
        old = conn.execute("SELECT id,status,job_id FROM settlement_imports WHERE source_sha256=%s", (sha,)).fetchone()
        if old:
            return clean(old)
        import_id = new_id()
        job = create_job(conn, user["id"], "reconcile", payload={"import_id": import_id})
        conn.execute(
            "INSERT INTO settlement_imports(id,raw,source_sha256,name,submitted_by,job_id) VALUES (%s,%s,%s,%s,%s,%s)",
            (import_id, raw, sha, name[:160], user["id"], job["id"]),
        )
        audit(conn, user["id"], "settlement.imported", import_id, {"sha256": sha})
        return {"id": import_id, "status": "queued", "job_id": job["id"]}

    return idempotent(conn, user["id"], key, {"op": "settlement_import", "sha256": sha}, operation)


def accept_settlement(conn, user, key, row_id):
    require(user, "approver")

    def operation():
        row = conn.execute("SELECT * FROM reconciliations WHERE id=%s FOR UPDATE", (row_id,)).fetchone()
        if not row:
            fail("RECONCILIATION_NOT_FOUND", "Reconciliation row not found.", 404)
        if row["classification"] != "MATCH" or row["state"] != "open":
            fail("NOT_SETTLEABLE", "Only an unresolved exact match can be accepted.", 409)
        rec = conn.execute("SELECT * FROM records WHERE id=%s FOR UPDATE", (row["record_id"],)).fetchone()
        if rec["state"] != "posted":
            fail("NOT_SETTLEABLE", "The obligation is already settled or reversed.", 409)
        journal = insert_journal(
            conn,
            rec,
            "settlement",
            row["data"]["proposal"],
            user["id"],
            settlement_reference=row["settlement_reference"],
        )
        conn.execute("UPDATE records SET state='settled' WHERE id=%s", (rec["id"],))
        conn.execute("UPDATE reconciliations SET state='accepted',actor=%s WHERE id=%s", (user["id"], row_id))
        audit(conn, user["id"], "settlement.accepted", row_id, {"journal_id": str(journal["id"])})
        return clean(journal)

    return idempotent(conn, user["id"], key, {"op": "accept", "row": str(row_id)}, operation)


def disposition(conn, user, key, row_id, reason):
    require(user, "operator", "approver")

    def operation():
        row = conn.execute("SELECT * FROM reconciliations WHERE id=%s FOR UPDATE", (row_id,)).fetchone()
        if not row:
            fail("RECONCILIATION_NOT_FOUND", "Reconciliation row not found.", 404)
        if row["state"] == "accepted":
            fail("ALREADY_ACCEPTED", "An accepted settlement cannot be rewritten.", 409)
        conn.execute(
            "UPDATE reconciliations SET state='reviewed',actor=%s,disposition=%s WHERE id=%s",
            (user["id"], reason, row_id),
        )
        audit(
            conn, user["id"], "exception.reviewed", row_id, {"reason": reason, "classification": row["classification"]}
        )
        row.update(state="reviewed", actor=user["id"], disposition=reason)
        return clean(row)

    return idempotent(conn, user["id"], key, {"op": "disposition", "row": str(row_id), "reason": reason}, operation)
