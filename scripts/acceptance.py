"""Real HTTP/worker acceptance sequence. Adds visibly synthetic verification batches."""

from __future__ import annotations
import json
import sys
import time
import urllib.error
import uuid
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
from client import Client
from fixtures.generate import detail, make_batch
from verify_evidence import verify


def forbidden(fn, status):
    try:
        fn()
    except urllib.error.HTTPError as exc:
        assert exc.code == status, (exc.code, exc.read())
    else:
        raise AssertionError(f"Expected HTTP {status}")


def main():
    started = time.perf_counter()
    token = uuid.uuid4().hex[:8].upper()
    clients = {role: Client() for role in ("operator", "approver", "auditor")}
    for role, client in clients.items():
        client.login(role)
    operator, approver, auditor = (clients[k] for k in ("operator", "approver", "auditor"))
    observations = []
    for mode in ("before_commit", "after_commit"):
        amounts = ["123.45", "0.02", "4000.00", "0.01", "3333.33", "3333.34", "0.00", "-1.00"]
        prefix = token + ("B" if mode == "before_commit" else "A")
        raw = make_batch(
            [detail(f"{prefix}-{i}", amount, source="VERIFY01") for i, amount in enumerate(amounts)],
            "RECOVERY-" + prefix,
        )
        key = "acceptance-" + prefix
        batch = operator.request("POST", "/batches", filename=f"verify-{prefix}.dat", raw=raw, key=key)
        repeated = operator.request("POST", "/batches", filename=f"verify-{prefix}.dat", raw=raw, key=key)
        assert repeated["id"] == batch["id"]
        reupload = operator.request("POST", "/batches", filename="renamed.dat", raw=raw)
        assert reupload["id"] == batch["id"]
        different = make_batch([detail(f"{prefix}-OTHER", "1.00", source="VERIFY01")])
        forbidden(lambda: operator.request("POST", "/batches", filename="conflict.dat", raw=different, key=key), 409)
        operator.wait(batch["job_id"])
        batch = operator.request("GET", "/batches/" + batch["id"])
        assert batch["status"] == "review" and batch["accepted_count"] == 6 and batch["rejected_count"] == 2
        records = operator.request("GET", f"/batches/{batch['id']}/records?page_size=100")["items"]
        for record, value in zip(records, amounts):
            if Decimal(value) > 0:
                expected = min(
                    Decimal("2500.00"),
                    (Decimal(value) * Decimal(".75")).quantize(Decimal(".01"), rounding=ROUND_HALF_UP),
                )
                assert record["payable"] == format(expected, ".2f")
            else:
                assert record["payable"] is None
        trace = operator.request("GET", "/records/" + records[0]["id"] + "/trace")
        assert trace["record"]["raw_hex"] == raw[81:161].hex()
        forbidden(lambda: operator.request("POST", f"/batches/{batch['id']}/approve", {}), 403)
        forbidden(lambda: operator.request("GET", f"/batches/{batch['id']}/evidence", binary=True), 403)
        approver.request("POST", f"/batches/{batch['id']}/approve", {})
        job = approver.request("POST", f"/batches/{batch['id']}/post", {"failure_mode": mode})
        finished = approver.wait(job["id"], timeout=90)
        assert len(finished["attempts"]) >= 2, "A real interruption must create abandoned/recovered attempts"
        ledger = operator.request("GET", "/ledger?q=" + prefix + "&page_size=100")["items"]
        assert len(ledger) == 6
        assert len({(j["source"], j["reference"]) for j in ledger}) == 6
        assert all(j["debit"] == "5100" and j["credit"] == "2100" and j["currency"] == "CAD" for j in ledger)
        digest = batch["result_digest"]
        before = len(ledger)
        replay = auditor.request("POST", f"/batches/{batch['id']}/replay", {})
        replay = auditor.wait(replay["id"])
        comparison = auditor.request("POST", f"/batches/{batch['id']}/compare", {})
        comparison = auditor.wait(comparison["id"])
        assert replay["result"]["same"] is True
        assert len(operator.request("GET", "/ledger?q=" + prefix + "&page_size=100")["items"]) == before
        observations.append(
            {
                "mode": mode,
                "batch_id": batch["id"],
                "accepted": 6,
                "rejected": 2,
                "attempts": finished["attempts"],
                "result_digest": digest,
                "replay": replay["result"],
                "comparison": comparison["result"],
                "journals": len(ledger),
            }
        )
    # A one-cent difference is retained as an exception; only an exact match may settle.
    refs = [r["reference"] for r in records]
    settlement = (
        "settlement_reference,source,reference,amount\n"
        f"VERIFY-{token}-1,VERIFY01,{refs[0]},92.59\n"
        f"VERIFY-{token}-2,VERIFY01,{refs[1]},0.03\n"
    ).encode()
    imported = operator.request("POST", "/reconciliation", filename="verification.csv", raw=settlement)
    operator.wait(imported["job_id"])
    rows = operator.request("GET", "/reconciliation?q=" + prefix + "&page_size=100")["items"]
    exact = next(r for r in rows if r["classification"] == "MATCH")
    mismatch = next(r for r in rows if r["classification"] == "AMOUNT_MISMATCH")
    assert mismatch["expected"] == "0.02" and mismatch["received"] == "0.03"
    forbidden(lambda: approver.request("POST", f"/reconciliation/{mismatch['id']}/accept", {}), 409)
    approver.request("POST", f"/reconciliation/{exact['id']}/accept", {})
    forbidden(lambda: approver.request("POST", f"/reconciliation/{exact['id']}/accept", {}), 409)
    approver.request(
        "POST",
        f"/reconciliation/{mismatch['id']}/disposition",
        {"reason": "Synthetic one-cent mismatch retained for investigation."},
    )
    journals = operator.request("GET", "/ledger?q=" + prefix + "&page_size=100")["items"]
    unsettled = next(j for j in journals if j["reference"] == refs[2] and j["kind"] == "obligation")
    reversal = approver.request(
        "POST", f"/ledger/{unsettled['id']}/reverse", {"reason": "Synthetic authorized correction."}
    )
    assert reversal["reversal_of"] == unsettled["id"]
    settled = next(j for j in journals if j["reference"] == refs[0] and j["kind"] == "obligation")
    forbidden(
        lambda: approver.request("POST", f"/ledger/{settled['id']}/reverse", {"reason": "Invalid settled correction."}),
        409,
    )
    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)
    bundle = output / "acceptance-evidence.zip"
    bundle.write_bytes(auditor.request("GET", f"/batches/{batch['id']}/evidence", binary=True))
    evidence = verify(bundle)
    assert operator.request("GET", "/audit/verify")["valid"]
    report = {
        "passed": True,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "workflow": observations,
        "evidence": evidence,
        "settlement": {"exact_match_settled": True, "one_cent_mismatch_retained": True, "reversal_verified": True},
        "authorization": {"operator_approval_denied": True, "operator_export_denied": True},
    }
    (output / "verification.json").write_text(json.dumps(report, indent=2))
    print(
        json.dumps(
            {
                "passed": True,
                "elapsed_seconds": report["elapsed_seconds"],
                "recovery_modes": len(observations),
                "evidence_files": evidence["files"],
            }
        )
    )


if __name__ == "__main__":
    main()
