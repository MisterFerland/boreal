"""Populate the console exclusively through authenticated API / real worker workflows."""

from __future__ import annotations
import json
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from client import Client, ROOT


def main():
    operator = Client()
    approver = Client()
    operator.login("operator")
    approver.login("approver")
    receipts = []
    fixtures = [("demo.dat", True), ("hand-check.dat", True), ("review.dat", False), ("pending.dat", False)]
    for filename, post in fixtures:
        path = ROOT / "fixtures" / filename
        raw = path.read_bytes()
        batch = operator.request(
            "POST", "/batches", filename=filename, raw=raw, key="seed-import-" + hashlib.sha256(raw).hexdigest()
        )
        operator.wait(batch["job_id"])
        batch = operator.request("GET", "/batches/" + batch["id"])
        if post and batch["status"] == "review":
            approver.request("POST", f"/batches/{batch['id']}/approve", {}, key="seed-approve-" + filename)
            job = approver.request("POST", f"/batches/{batch['id']}/post", {}, key="seed-post-" + filename)
            approver.wait(job["id"])
        receipts.append({"file": filename, "batch_id": batch["id"]})
    settlement = ROOT / "fixtures" / "settlement.csv"
    raw = settlement.read_bytes()
    result = operator.request(
        "POST",
        "/reconciliation",
        filename=settlement.name,
        raw=raw,
        key="seed-settlement-" + hashlib.sha256(raw).hexdigest(),
    )
    operator.wait(result["job_id"])
    matches = approver.request("GET", "/reconciliation?classification=MATCH&page_size=100")["items"]
    for row in matches:
        if row.get("state") == "open":
            approver.request("POST", f"/reconciliation/{row['id']}/accept", {}, key="seed-accept-" + row["id"])
    report = {
        "description": "Seeded through authenticated API and native COBOL worker",
        "batches": receipts,
        "overview": operator.request("GET", "/overview"),
    }
    (ROOT / ".local" / "seed.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"Prepared {len(receipts)} real demonstration batches and synthetic settlement worklist.")


if __name__ == "__main__":
    main()
