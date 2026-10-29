"""Real PostgreSQL + compiled COBOL + process-worker integration gates.

Uses a newly created, uniquely named disposable database. It never resets the
populated console database. BOREAL_TEST_ADMIN_URL supports CI; the optional local
runtime's private credential file supplies the same capability on this machine.
"""

import io
import json
import os
import secrets
import subprocess
import sys
import time
import uuid
import zipfile
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def database_url(url, name):
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, "/" + name, parts.query, parts.fragment))


@pytest.fixture(scope="module", autouse=True)
def isolated_database():
    admin = os.environ.get("BOREAL_TEST_ADMIN_URL")
    if not admin and (ROOT / ".local/runtime.json").exists():
        config = json.loads((ROOT / ".local/runtime.json").read_text())
        admin = f"postgresql://boreal_admin:{config['admin']}@127.0.0.1:55432/postgres"
    if not admin:
        pytest.skip("Real PostgreSQL test admin URL unavailable; no embedded database substitution")
    old = dict(os.environ)
    name = "boreal_test_" + uuid.uuid4().hex[:12]
    migration = os.environ.get("BOREAL_MIGRATION_URL", admin)
    runtime = os.environ.get("BOREAL_DATABASE_URL", admin)
    owner = urlsplit(migration).username
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(name), sql.Identifier(owner)))
    os.environ.update(
        BOREAL_DATABASE_URL=database_url(runtime, name),
        BOREAL_MIGRATION_URL=database_url(migration, name),
        BOREAL_LEASE_SECONDS="3",
        BOREAL_CHUNK_SIZE="2",
        BOREAL_DEMO="1",
        BOREAL_ORIGIN="http://127.0.0.1:8000",
    )
    from boreal.manage import migrate

    migrate()
    yield name
    os.environ.clear()
    os.environ.update(old)
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture(scope="module")
def clients(isolated_database):
    from boreal.api import app
    from boreal.auth import PASSWORD_HASHER
    from boreal.db import connect

    result = {}
    with connect(migration=True) as conn:
        for role in ("operator", "approver", "auditor"):
            password = secrets.token_urlsafe(20)
            conn.execute(
                "INSERT INTO users(id,username,role,password_hash) VALUES (%s,%s,%s,%s)",
                (role, role, role, PASSWORD_HASHER.hash(password)),
            )
            result[role] = {"password": password}
    for role in result:
        client = TestClient(app, base_url="http://127.0.0.1:8000")
        response = client.post("/api/auth/login", json={"username": role, "password": result[role]["password"]})
        assert response.status_code == 200, response.text
        client.headers["X-CSRF-Token"] = response.json()["csrf"]
        result[role]["client"] = client
    yield {role: value["client"] for role, value in result.items()}
    for value in result.values():
        value["client"].close()


def request(client, path, body=None, *, key=None):
    return client.post("/api" + path, json=body or {}, headers={"Idempotency-Key": key or uuid.uuid4().hex})


def file_bytes(amounts=("123.45", "0.02", "4000.00"), prefix=None):
    prefix = prefix or uuid.uuid4().hex[:9].upper()
    header = ("H" + "BOREAL01" + ("TEST-" + prefix).ljust(24) + "20261029" + " " * 39).encode()
    rows = []
    for index, amount in enumerate(amounts):
        cost = Decimal(amount)
        rows.append(
            (
                "D"
                + "TST00001"
                + f"{prefix}-{index}".ljust(20)
                + "CIR1"
                + "20261029"
                + f"{cost:+011.2f}"
                + "SYNTHETIC-COMMUNITY".ljust(28)
            ).encode()
        )
    trailer = ("T" + f"{len(rows):09d}" + f"{sum(map(Decimal, amounts)):+017.2f}" + " " * 53).encode()
    assert all(len(row) == 80 for row in [header, *rows, trailer])
    return b"\n".join([header, *rows, trailer]) + b"\n"


def run_worker(*, check=True, extra=None):
    env = {**os.environ, "PYTHONPATH": str(ROOT / "backend") + os.pathsep + str(ROOT), **(extra or {})}
    result = subprocess.run(
        [sys.executable, "-m", "boreal.worker", "--once"], cwd=ROOT, env=env, capture_output=True, timeout=60
    )
    if check:
        assert result.returncode == 0, result.stderr.decode()
    return result


def import_file(clients, raw=None, name="test.dat", key=None):
    response = clients["operator"].post(
        "/api/batches",
        files={"file": (name, raw or file_bytes(), "application/octet-stream")},
        headers={"Idempotency-Key": key or uuid.uuid4().hex},
    )
    assert response.status_code == 200, response.text
    return response.json()


def calculated(clients, raw=None, name="test.dat"):
    batch = import_file(clients, raw, name)
    run_worker()
    response = clients["operator"].get("/api/batches/" + batch["id"])
    assert response.status_code == 200, response.text
    batch = response.json()
    assert batch["status"] == "review", batch
    return batch


def approved(clients, raw=None):
    batch = calculated(clients, raw)
    response = request(clients["approver"], f"/batches/{batch['id']}/approve")
    assert response.status_code == 200, response.text
    return batch


def posted(clients, raw=None):
    batch = approved(clients, raw)
    job = request(clients["approver"], f"/batches/{batch['id']}/post").json()
    run_worker()
    assert clients["operator"].get("/api/jobs/" + job["id"]).json()["status"] == "succeeded"
    return batch


def test_exact_financial_path_and_rejections(clients):
    raw = file_bytes(("123.45", "0.02", "4000.00", "0.00", "-1.00", "3333.33", "3333.34"))
    batch = calculated(clients, raw)
    assert batch["accepted_count"] == 5
    assert batch["rejected_count"] == 2
    accepted = [r["payable"] for r in batch["records"] if r["reason"] == "ACCEPTED"]
    assert accepted == ["92.59", "0.02", "2500.00", "2500.00", "2500.00"]
    assert batch["control_total"] == "10789.14"
    assert batch["payable_total"] == "7592.61"
    record = batch["records"][0]
    trace = clients["operator"].get("/api/records/" + record["id"] + "/trace").json()
    assert trace["record"]["trace"]["unrounded"] == "92.5875"
    assert trace["record"]["raw_hex"] == raw.splitlines()[1].hex()
    source = clients["operator"].get(trace["source_url"])
    assert source.status_code == 200
    assert "compute" in source.text.lower()


def test_file_idempotency_and_request_conflict(clients):
    raw = file_bytes()
    key = uuid.uuid4().hex
    first = import_file(clients, raw, key=key)
    second = import_file(clients, raw, key=key)
    assert first == second
    assert import_file(clients, raw)["id"] == first["id"]
    conflict = clients["operator"].post(
        "/api/batches", files={"file": ("changed.dat", file_bytes())}, headers={"Idempotency-Key": key}
    )
    assert conflict.status_code == 409
    run_worker()


def test_bad_envelope_quarantines_no_records(clients):
    raw = file_bytes()
    batch = import_file(clients, raw[:-3])
    run_worker()
    result = clients["operator"].get("/api/batches/" + batch["id"]).json()
    assert result["status"] == "quarantined"
    assert result["records"] == []
    assert request(clients["approver"], f"/batches/{batch['id']}/approve").status_code == 409


def test_roles_csrf_and_separation(clients):
    batch = calculated(clients)
    assert request(clients["operator"], f"/batches/{batch['id']}/approve").status_code == 403
    assert request(clients["auditor"], f"/batches/{batch['id']}/approve").status_code == 403
    no_csrf = clients["approver"].post(
        "/api/batches/" + batch["id"] + "/approve",
        json={},
        headers={"X-CSRF-Token": "bad", "Idempotency-Key": uuid.uuid4().hex},
    )
    assert no_csrf.status_code == 403
    cross = clients["approver"].post(
        "/api/batches/" + batch["id"] + "/approve",
        json={},
        headers={"Origin": "https://evil.invalid", "Idempotency-Key": uuid.uuid4().hex},
    )
    assert cross.status_code == 403
    from boreal.db import connect

    with connect(migration=True) as conn:
        conn.execute("UPDATE users SET role='approver' WHERE id='operator'")
    try:
        denied = request(clients["operator"], f"/batches/{batch['id']}/approve")
        assert denied.status_code == 403
        assert denied.json()["detail"]["code"] == "SELF_APPROVAL"
    finally:
        with connect(migration=True) as conn:
            conn.execute("UPDATE users SET role='operator' WHERE id='operator'")
    for role in ("operator", "approver"):
        assert clients[role].get("/api/batches/" + batch["id"] + "/evidence").status_code == 403


@pytest.mark.parametrize("mode,committed_before_recovery", [("before_commit", 0), ("after_commit", 2)])
def test_real_crash_recovery_without_duplicate_effects(clients, mode, committed_before_recovery):
    from boreal.db import connect

    batch = approved(clients)
    response = request(clients["approver"], f"/batches/{batch['id']}/post", {"failure_mode": mode})
    assert response.status_code == 200, response.text
    job = response.json()
    crashed = run_worker(check=False)
    assert crashed.returncode == {"before_commit": 86, "after_commit": 87}[mode], crashed.stderr.decode()
    with connect() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM journals WHERE batch_id=%s", (batch["id"],)).fetchone()["n"]
            == committed_before_recovery
        )
    time.sleep(3.2)
    run_worker()
    result = clients["operator"].get("/api/jobs/" + job["id"]).json()
    assert result["status"] == "succeeded", result
    assert result["completed"] == 3
    assert len(result["attempts"]) == 2
    assert result["attempts"][0]["outcome"] == "abandoned"
    with connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM journals WHERE batch_id=%s", (batch["id"],)).fetchone()["n"] == 3
        assert conn.execute("SELECT count(*) AS n FROM receipts WHERE job_id=%s", (job["id"],)).fetchone()["n"] == 2


def test_competing_worker_processes(clients):
    from boreal.db import connect

    batch = approved(clients)
    job = request(clients["approver"], f"/batches/{batch['id']}/post").json()
    env = {**os.environ, "PYTHONPATH": str(ROOT / "backend") + os.pathsep + str(ROOT)}
    workers = [
        subprocess.Popen(
            [sys.executable, "-m", "boreal.worker", "--once"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(2)
    ]
    for worker in workers:
        _, stderr = worker.communicate(timeout=60)
        assert worker.returncode == 0, stderr.decode()
    assert clients["operator"].get("/api/jobs/" + job["id"]).json()["status"] == "succeeded"
    with connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM journals WHERE batch_id=%s", (batch["id"],)).fetchone()["n"] == 3


def test_stale_fence_cannot_commit(clients):
    from boreal.db import connect
    from boreal import worker

    batch = approved(clients)
    job = request(clients["approver"], f"/batches/{batch['id']}/post").json()
    stale = worker.claim()
    assert str(stale["id"]) == job["id"]
    with connect() as conn:
        conn.execute("UPDATE jobs SET lease_until=now()-interval '1 second' WHERE id=%s", (job["id"],))
    fresh = worker.claim()
    assert fresh["fence"] > stale["fence"]
    with pytest.raises(worker.ClaimLost), connect() as conn:
        worker.assert_claim(conn, stale)
    with connect() as conn:
        conn.execute("UPDATE jobs SET lease_until=now()-interval '1 second' WHERE id=%s", (job["id"],))
    run_worker()
    assert clients["operator"].get("/api/jobs/" + job["id"]).json()["status"] == "succeeded"


def test_frozen_journals_reversal_and_business_uniqueness(clients):
    from boreal.db import connect

    raw = file_bytes()
    batch = posted(clients, raw)
    with connect() as conn:
        journals = conn.execute("SELECT * FROM journals WHERE batch_id=%s", (batch["id"],)).fetchall()
    for row in journals:
        assert row["debit"] == "5100" and row["credit"] == "2100"
        assert row["currency"] == "CAD" and row["amount"] > 0
    with pytest.raises(psycopg.Error), connect() as conn:
        conn.execute("UPDATE journals SET amount=1 WHERE id=%s", (journals[0]["id"],))
    with pytest.raises(psycopg.Error), connect() as conn:
        conn.execute("DELETE FROM journals WHERE id=%s", (journals[0]["id"],))
    with pytest.raises(psycopg.Error), connect() as conn:
        conn.execute("UPDATE records SET data='{}' WHERE id=%s", (journals[0]["record_id"],))
    reversal = request(
        clients["approver"],
        "/ledger/" + str(journals[0]["id"]) + "/reverse",
        {"reason": "Synthetic correction of approved instruction"},
    )
    assert reversal.status_code == 200, reversal.text
    assert reversal.json()["reversal_of"] == str(journals[0]["id"])
    assert reversal.json()["debit"] == "2100" and reversal.json()["credit"] == "5100"
    assert (
        request(
            clients["approver"], "/ledger/" + str(journals[0]["id"]) + "/reverse", {"reason": "Repeated correction"}
        ).status_code
        == 409
    )
    # Changed header creates a different file hash, but the same business identities.
    changed = raw.replace(b"TEST-", b"COPY-", 1)
    duplicate = calculated(clients, changed)
    assert duplicate["accepted_count"] == 0
    assert all(r["reason"] == "BUSINESS_KEY_CONFLICT" for r in duplicate["records"])


def test_reconciliation_one_cent_duplicate_missing_unexpected(clients):
    from boreal.db import connect

    batch = posted(clients)
    a, b, c = batch["records"]
    raw = (
        "settlement_reference,source,reference,amount\n"
        f"SET-{uuid.uuid4().hex[:8]},{a['source']},{a['reference']},92.59\n"
        f"MISMATCH-{uuid.uuid4().hex[:8]},{b['source']},{b['reference']},0.03\n"
        f"UNKNOWN-{uuid.uuid4().hex[:8]},TST00001,UNKNOWN,12.00\n"
    ).encode()
    # Repeat the first reference to create a distinct duplicate classification.
    raw += raw.splitlines()[1] + b"\n"
    response = clients["operator"].post(
        "/api/reconciliation", files={"file": ("settlement.csv", raw)}, headers={"Idempotency-Key": uuid.uuid4().hex}
    )
    assert response.status_code == 200, response.text
    imported = response.json()
    run_worker()
    result = clients["operator"].get("/api/jobs/" + imported["job_id"]).json()
    assert result["status"] == "succeeded", result
    with connect() as conn:
        rows = conn.execute("SELECT * FROM reconciliations WHERE import_id=%s", (imported["id"],)).fetchall()
    assert {"MATCH", "AMOUNT_MISMATCH", "DUPLICATE", "MISSING", "UNEXPECTED"} <= {r["classification"] for r in rows}
    match = next(r for r in rows if r["classification"] == "MATCH")
    mismatch = next(r for r in rows if r["classification"] == "AMOUNT_MISMATCH")
    assert str(mismatch["expected"]) == "0.02" and str(mismatch["received"]) == "0.03"
    assert request(clients["approver"], "/reconciliation/" + str(mismatch["id"]) + "/accept").status_code == 409
    assert request(clients["approver"], "/reconciliation/" + str(match["id"]) + "/accept").status_code == 200
    assert request(clients["approver"], "/reconciliation/" + str(match["id"]) + "/accept").status_code == 409
    disposition = request(
        clients["operator"],
        "/reconciliation/" + str(mismatch["id"]) + "/disposition",
        {"reason": "One cent disagreement retained for review"},
    )
    assert disposition.status_code == 200
    assert disposition.json()["classification"] == "AMOUNT_MISMATCH"
    with connect() as conn:
        journal = conn.execute(
            "SELECT * FROM journals WHERE record_id=%s AND kind='obligation'", (match["record_id"],)
        ).fetchone()
    assert (
        request(
            clients["approver"],
            "/ledger/" + str(journal["id"]) + "/reverse",
            {"reason": "Attempted settled correction"},
        ).status_code
        == 409
    )
    repeat = clients["operator"].post(
        "/api/reconciliation", files={"file": ("settlement.csv", raw)}, headers={"Idempotency-Key": uuid.uuid4().hex}
    )
    assert repeat.json()["id"] == imported["id"]


def test_replay_comparison_no_financial_effect_and_evidence(clients, tmp_path):
    from boreal.db import connect
    from boreal.common import digest

    batch = posted(clients)
    with connect() as conn:
        before = conn.execute("SELECT count(*) AS n FROM journals").fetchone()["n"]
    replay = request(clients["auditor"], f"/batches/{batch['id']}/replay").json()
    run_worker()
    result = clients["auditor"].get("/api/jobs/" + replay["id"]).json()["result"]
    assert result["same"] and result["differences"] == []
    assert result["original_digest"] == result["replay_digest"] == batch["result_digest"]
    comparison = request(clients["operator"], f"/batches/{batch['id']}/compare").json()
    run_worker()
    result = clients["operator"].get("/api/jobs/" + comparison["id"]).json()["result"]
    assert result["v1_total"] == "2592.61"
    assert result["v2_total"] == "2598.78"
    assert result["delta"] == "6.17"
    with connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM journals").fetchone()["n"] == before
    response = clients["auditor"].get("/api/batches/" + batch["id"] + "/evidence")
    assert response.status_code == 200, response.text if response.status_code != 200 else ""
    import hashlib

    with zipfile.ZipFile(io.BytesIO(response.content)) as bundle:
        manifest = json.loads(bundle.read("manifest.json"))
        for name, expected in manifest["files"].items():
            assert hashlib.sha256(bundle.read(name)).hexdigest() == expected
        assert digest(json.loads(bundle.read("calculation.json"))) == batch["result_digest"]
        assert json.loads(bundle.read("audit-verification.json"))["valid"]
        assert "input/original.dat" in bundle.namelist()
        assert any(name.endswith(".cob") for name in bundle.namelist())
        bundle.extractall(tmp_path)
    replayed = subprocess.run(
        [sys.executable, str(tmp_path / "repository/engine/replay_evidence.py"), str(tmp_path)],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": ""},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert replayed.returncode == 0, replayed.stderr
    assert json.loads(replayed.stdout)["verified"] is True
    assert clients["auditor"].get("/api/audit/verify").json()["valid"]


def test_engine_failure_cannot_report_success(clients):
    batch = import_file(clients)
    run_worker(extra={"BOREAL_ENGINE_BUILDS": "/nonexistent/boreal-engine-builds"})
    job = clients["operator"].get("/api/jobs/" + batch["job_id"]).json()
    assert job["status"] == "retry"
    assert "ENGINE_UNAVAILABLE" in job["error"]
    assert clients["operator"].get("/api/batches/" + batch["id"]).json()["result_digest"] is None
    run_worker()
    assert clients["operator"].get("/api/jobs/" + batch["job_id"]).json()["status"] == "succeeded"


def test_mixed_format_original_bytes_and_bad_nibbles(clients):
    batch = calculated(clients, (ROOT / "fixtures/mixed-valid.bin").read_bytes(), name="mixed-valid.bin")
    assert batch["schema_version"] == "BOREAL-MIXED01"
    assert len(batch["records"][0]["raw_hex"]) == 146
    bad = import_file(clients, (ROOT / "fixtures/mixed-invalid-digit.bin").read_bytes(), name="mixed-invalid.bin")
    run_worker()
    result = clients["operator"].get("/api/batches/" + bad["id"]).json()
    assert result["status"] == "quarantined"
    assert result["records"] == []


def test_login_throttle_and_path_allowlist(clients):
    from boreal.api import app

    with TestClient(app, base_url="http://127.0.0.1:8000") as anonymous:
        assert anonymous.get("/api/ledger").status_code == 401
        for _ in range(5):
            assert (
                anonymous.post("/api/auth/login", json={"username": "missing-user", "password": "invalid"}).status_code
                == 401
            )
        assert (
            anonymous.post("/api/auth/login", json={"username": "missing-user", "password": "invalid"}).status_code
            == 429
        )
    assert clients["operator"].get("/api/engine/source/invalid/passwd").status_code == 404
    assert clients["operator"].get("/api/fixtures/.env").status_code == 404


def test_database_closes_null_checks_and_frozen_record_append(clients):
    from boreal.db import connect
    from boreal.common import jsonb

    batch = import_file(clients)
    with pytest.raises(psycopg.errors.CheckViolation), connect() as conn:
        conn.execute("UPDATE batches SET status='calculating' WHERE id=%s", (batch["id"],))
        conn.execute(
            """INSERT INTO records(id,batch_id,position,source,reference,reason,eligible_cost,payable,state,data)
         VALUES (%s,%s,2,'TST00001','INJECTED','ACCEPTED',1,1,'accepted','{}')""",
            (str(uuid.uuid4()), batch["id"]),
        )
    run_worker()
    original = clients["operator"].get("/api/batches/" + batch["id"]).json()["records"][0]
    with pytest.raises(psycopg.Error), connect() as conn:
        data = {k: v for k, v in original.items() if k not in ("id", "batch_id", "state")}
        data["position"] = 900
        conn.execute(
            """INSERT INTO records(id,batch_id,position,source,reference,reason,eligible_cost,payable,state,data)
         VALUES (%s,%s,900,%s,%s,'ACCEPTED',%s,%s,'accepted',%s)""",
            (
                str(uuid.uuid4()),
                batch["id"],
                original["source"],
                original["reference"],
                original["eligible_cost"],
                original["payable"],
                jsonb(data),
            ),
        )
    with pytest.raises(psycopg.Error), connect() as conn:
        conn.execute("UPDATE records SET state='posted' WHERE id=%s", (original["id"],))


def test_interleaved_export_and_audit_writer_preserves_chain(clients, monkeypatch):
    from boreal import api
    from boreal.common import audit as append_audit
    from boreal.db import connect

    batch = calculated(clients)

    def interleave(conn, actor, action, subject, details=None):
        # A second transaction commits after export has read its batch, before
        # the exporter obtains the global chain lock. This caught a real RR bug.
        with connect() as other:
            append_audit(other, "test-writer", "concurrent.event", "audit-regression")
        append_audit(conn, actor, action, subject, details)

    monkeypatch.setattr(api, "audit", interleave)
    exported = clients["auditor"].get("/api/batches/" + batch["id"] + "/evidence")
    assert exported.status_code == 200
    with zipfile.ZipFile(io.BytesIO(exported.content)) as bundle:
        assert json.loads(bundle.read("audit-verification.json"))["valid"]
    assert clients["auditor"].get("/api/audit/verify").json()["valid"]


def test_abandoned_final_claim_becomes_failed_and_explicit_retry_recovers(clients):
    from boreal import worker
    from boreal.db import connect

    batch = import_file(clients)
    claimed = worker.claim()
    assert str(claimed["id"]) == batch["job_id"]
    with connect() as conn:
        conn.execute("UPDATE batches SET status='calculating' WHERE id=%s", (batch["id"],))
        conn.execute(
            "UPDATE jobs SET max_attempts=1,lease_until=now()-interval '1 second' WHERE id=%s", (claimed["id"],)
        )
    assert worker.claim() is None
    job = clients["operator"].get("/api/jobs/" + batch["job_id"]).json()
    assert job["status"] == "failed" and job["attempts"][-1]["outcome"] == "abandoned"
    assert clients["operator"].get("/api/batches/" + batch["id"]).json()["status"] == "failed"
    assert request(clients["operator"], "/jobs/" + batch["job_id"] + "/retry").status_code == 200
    run_worker()
    assert clients["operator"].get("/api/jobs/" + batch["job_id"]).json()["status"] == "succeeded"
