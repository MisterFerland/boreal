"""Independently verify ZIP membership hashes, financial digest, balances and audit chain."""

from __future__ import annotations
import argparse
import hashlib
import json
import re
from decimal import Decimal
from pathlib import PurePosixPath
import zipfile


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate ZIP entries")
        for name in names:
            if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts or "\\" in name:
                raise ValueError("Unsafe ZIP member")
        manifest = json.loads(archive.read("manifest.json"))
        require(set(names) == set(manifest["files"]) | {"manifest.json"}, "Unlisted/missing evidence files")
        for name, expected in manifest["files"].items():
            require(hashlib.sha256(archive.read(name)).hexdigest() == expected, f"Hash mismatch: {name}")
        require(
            hashlib.sha256(archive.read("input/original.dat")).hexdigest() == manifest["input_sha256"],
            "Original input hash mismatch",
        )
        calculations = json.loads(archive.read("calculation.json"))
        require(
            hashlib.sha256(canonical(calculations).encode()).hexdigest() == manifest["financial_result_digest"],
            "Financial digest mismatch",
        )
        journals = json.loads(archive.read("journals.json"))
        accepted = {(row["source"], row["reference"]): row for row in calculations if row["reason"] == "ACCEPTED"}
        seen = set()
        indexed = {row["id"]: row for row in journals}
        pairs = {"obligation": ("5100", "2100"), "settlement": ("2100", "1100"), "reversal": ("2100", "5100")}
        for row in journals:
            require(
                isinstance(row["amount"], str) and re.fullmatch(r"\d+\.\d{2}", row["amount"]),
                "Invalid monetary representation",
            )
            require(Decimal("0.00") < Decimal(row["amount"]) <= Decimal("2500.00"), "Invalid journal amount")
            require(row["currency"] == "CAD", "Unsupported currency")
            require(pairs.get(row["kind"]) == (row["debit"], row["credit"]), "Invalid journal account pair")
            identity = (row["source"], row["reference"])
            require(
                identity in accepted and row["amount"] == accepted[identity]["payable"],
                "Journal differs from approved financial result",
            )
            key = (row["kind"], *identity)
            require(key not in seen, "Duplicate committed business effect")
            seen.add(key)
            if row["kind"] == "reversal":
                original = indexed.get(row["reversal_of"])
                require(
                    original and original["kind"] == "obligation" and original["record_id"] == row["record_id"],
                    "Invalid reversal linkage",
                )
        audit = json.loads(archive.read("audit.json"))
        previous = "0" * 64
        last_sequence = 0
        for row in audit:
            require(row["sequence"] > last_sequence, "Audit order mismatch")
            require(row["previous_hash"] == previous, "Audit predecessor mismatch")
            expected = hashlib.sha256((previous + "\n" + canonical(row["event"])).encode()).hexdigest()
            require(row["hash"] == expected, f"Audit mismatch at {row['sequence']}")
            previous = row["hash"]
            last_sequence = row["sequence"]
        checkpoint = json.loads(archive.read("audit-verification.json"))
        require(
            checkpoint["valid"] and checkpoint["head"] == previous and checkpoint["count"] == len(audit),
            "Audit checkpoint mismatch",
        )
        return {
            "valid": True,
            "files": len(names),
            "journals": len(journals),
            "audit_events": len(audit),
            "financial_result_digest": manifest["financial_result_digest"],
            "head": previous,
            "limitation": "Detects changes relative to this manifest and chain anchor; cannot defeat a privileged rewrite of both.",
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle")
    args = parser.parse_args()
    print(json.dumps(verify(args.bundle), indent=2))
