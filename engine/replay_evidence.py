"""Replay a BOREAL evidence ZIP or extracted bundle using its retained build.

Run: python engine/replay_evidence.py /path/to/evidence.zip
Requires the delivered Linux x86_64 libcob runtime. No database is accessed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from boreal import engine

FINANCIAL_KEYS = (
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


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def financial(records):
    return [{key: row.get(key) for key in FINANCIAL_KEYS} for row in sorted(records, key=lambda row: row["position"])]


def safe_member(name):
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        raise ValueError("Unsafe evidence member name")
    member = PurePosixPath(name)
    if (
        not member.parts
        or member.is_absolute()
        or str(member) != name
        or any(part in ("..", ".") or ":" in part for part in member.parts)
    ):
        raise ValueError("Unsafe evidence member path")
    return member


def extract_verified_zip(path, destination):
    """Validate membership and every byte before writing anything to a private directory."""
    maximum_total = 512 * 1024 * 1024
    maximum_member = 256 * 1024 * 1024
    with zipfile.ZipFile(path) as bundle:
        members = bundle.infolist()
        names = [member.filename for member in members]
        if len(members) > 2048 or len(names) != len(set(names)):
            raise ValueError("Duplicate or excessive ZIP members")
        if sum(member.file_size for member in members) > maximum_total:
            raise ValueError("Evidence ZIP exceeds the decompressed size limit")
        for member in members:
            safe_member(member.filename)
            file_type = stat.S_IFMT(member.external_attr >> 16)
            if member.is_dir() or file_type not in (0, stat.S_IFREG) or member.flag_bits & 1:
                raise ValueError("ZIP links, special files, directories and encryption are not supported")
            if member.file_size > maximum_member:
                raise ValueError("Evidence member exceeds the size limit")
        if "manifest.json" not in names or bundle.getinfo("manifest.json").file_size > 1024 * 1024:
            raise ValueError("Missing or oversized evidence manifest")
        manifest_bytes = bundle.read("manifest.json")
        manifest = json.loads(manifest_bytes)
        expected_files = manifest.get("files")
        if not isinstance(expected_files, dict) or set(names) != set(expected_files) | {"manifest.json"}:
            raise ValueError("Unlisted or missing evidence members")
        for name, expected in expected_files.items():
            safe_member(name)
            if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
                raise ValueError("Invalid evidence digest")
            checksum = hashlib.sha256()
            with bundle.open(name) as source:
                for block in iter(lambda: source.read(65536), b""):
                    checksum.update(block)
            if checksum.hexdigest() != expected:
                raise ValueError(f"Evidence hash mismatch: {name}")
        # All members have now passed path, membership, size and digest checks.
        # Recheck bytes while copying to reject any concurrent archive mutation.
        for member in members:
            target = destination.joinpath(*safe_member(member.filename).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            checksum = hashlib.sha256()
            with bundle.open(member) as source, target.open("xb") as output:
                for block in iter(lambda: source.read(65536), b""):
                    checksum.update(block)
                    output.write(block)
            expected = (
                hashlib.sha256(manifest_bytes).hexdigest()
                if member.filename == "manifest.json"
                else expected_files[member.filename]
            )
            if checksum.hexdigest() != expected:
                raise ValueError("Evidence changed during extraction")


def replay(path):
    path = Path(path).resolve()
    if path.is_file():
        with tempfile.TemporaryDirectory(prefix="boreal-evidence-replay-") as temporary:
            directory = Path(temporary)
            extract_verified_zip(path, directory)
            return replay_directory(directory)
    return replay_directory(path)


def replay_directory(directory):
    directory = Path(directory).resolve()
    manifest = json.loads((directory / "manifest.json").read_text())
    for name, expected in manifest["files"].items():
        safe_member(name)
        path = (directory / name).resolve()
        if not path.is_relative_to(directory) or not path.is_file():
            raise ValueError("Evidence member is missing or outside the bundle")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Evidence hash mismatch: {name}")
    batch = json.loads((directory / "batch.json").read_text())
    snapshot = json.loads((directory / "reference-snapshot.json").read_text())
    original = json.loads((directory / "calculation.json").read_text())
    build = manifest["engine_build"]
    if not re.fullmatch(r"[a-f0-9]{20}", build):
        raise ValueError("Invalid recorded build identifier")
    archive = directory / "engine" / build
    # ZIP extraction does not reliably restore Unix executable permissions.
    # Enable only the exact six hash-verified native files listed by the build.
    info = json.loads((archive / "manifest.json").read_text())
    for name, expected in info["executables"].items():
        if name not in {"batch", "envelope", "reconcile", "packed", "aggregate", "reverse"}:
            raise ValueError("Unrecognized executable in build manifest")
        binary = archive / name
        if binary.is_symlink() or hashlib.sha256(binary.read_bytes()).hexdigest() != expected:
            raise ValueError("Native executable integrity failure")
        binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
    raw = (directory / "input" / "original.dat").read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["input_sha256"]:
        raise ValueError("Original input digest differs")
    previous = os.environ.get("BOREAL_ENGINE_BUILDS")
    os.environ["BOREAL_ENGINE_BUILDS"] = str(directory / "engine")
    try:
        mixed = batch["schema_version"] == "BOREAL-MIXED01"
        normalized = engine.decode_mixed(raw, build) if mixed else raw
        result = engine.calculate(normalized, batch["policy"], build)
        if result["status"] != "verified":
            raise ValueError("Archived input failed COBOL envelope verification")
        conflicts = set(snapshot.get("conflicting_positions", []))
        for row in result["records"]:
            if mixed:
                start = 81 + (row["position"] - 2) * 74
                row["raw_hex"] = raw[start : start + 73].hex()
            if row["position"] in conflicts:
                row.update(reason="BUSINESS_KEY_CONFLICT", payable=None, proposal=None)
        recomputed = financial(result["records"])
        replay_digest = hashlib.sha256(canonical(recomputed).encode()).hexdigest()
        if len(original) != len(recomputed):
            raise ValueError("Replay result count differs from recorded snapshot")
        differences = [
            {"position": old["position"], "before": old, "after": new}
            for old, new in zip(original, recomputed, strict=True)
            if old != new
        ]
        total = engine.aggregate([row["payable"] for row in recomputed if row.get("payable")], build)
        verified = replay_digest == manifest["financial_result_digest"] and not differences
        return {
            "verified": verified,
            "engine_build": build,
            "policy": batch["policy"],
            "records": len(recomputed),
            "payable_total": total,
            "original_digest": manifest["financial_result_digest"],
            "replay_digest": replay_digest,
            "differences": differences,
            "side_effects": "No database, approval or journal writes.",
        }
    finally:
        if previous is None:
            os.environ.pop("BOREAL_ENGINE_BUILDS", None)
        else:
            os.environ["BOREAL_ENGINE_BUILDS"] = previous


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", help="Evidence ZIP or extracted bundle directory")
    result = replay(parser.parse_args().bundle)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if result["verified"] else 1)
