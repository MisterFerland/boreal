"""Strict transport boundary to retained, native COBOL executables.

No policy, rounding, journal or reconciliation fallback exists here.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "engine"
CHUNK_SIZE = 500
MAX_INPUT_BYTES = 32 * 1024 * 1024
MAX_OUTPUT_BYTES = 2 * 1024 * 1024


class EngineError(RuntimeError):
    """An observable engine, protocol, framing or binary-decoding failure."""


def _build_directory(build_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{20}", build_id):
        raise EngineError("ENGINE_BUILD_INVALID")
    return Path(os.environ.get("BOREAL_ENGINE_BUILDS", ENGINE / "builds")) / build_id


def build_info(build_id: str | None = None) -> dict:
    try:
        path = _build_directory(build_id) / "manifest.json" if build_id else ENGINE / "build.json"
        result = json.loads(path.read_text())
        if build_id is not None and result["engine_build"] != build_id:
            raise EngineError("ENGINE_BUILD_IDENTITY_MISMATCH")
        directory = _build_directory(result["engine_build"])
        programs = {"batch", "envelope", "reconcile", "packed", "aggregate", "reverse"}
        if set(result["executables"]) != programs:
            raise EngineError("ENGINE_MANIFEST_INVALID")
        result["available"] = True
        for name, expected in result["executables"].items():
            binary = directory / name
            if not binary.is_file():
                result.update(available=False, integrity_error="ENGINE_UNAVAILABLE")
                break
            if binary.is_symlink() or hashlib.sha256(binary.read_bytes()).hexdigest() != expected:
                result.update(available=False, integrity_error="ENGINE_BUILD_HASH_MISMATCH")
                break
        return result
    except (OSError, ValueError, KeyError, EngineError) as exc:
        return {
            "engine_build": build_id or "unavailable",
            "available": False,
            "compiler": "unavailable",
            "source_hash": None,
            "executable_hash": None,
            "integrity_error": str(exc) if isinstance(exc, EngineError) else "ENGINE_UNAVAILABLE",
        }


def _run(
    program: str, payload: bytes, policy: str | None = None, build_id: str | None = None
) -> tuple[list[str], dict]:
    if program not in {"batch", "envelope", "reconcile", "packed", "aggregate", "reverse"}:
        raise EngineError("ENGINE_PROGRAM_INVALID")
    info = build_info(build_id)
    if not info["available"]:
        raise EngineError(info.get("integrity_error", "ENGINE_UNAVAILABLE"))
    executable = _build_directory(info["engine_build"]) / program
    if hashlib.sha256(executable.read_bytes()).hexdigest() != info["executables"][program]:
        raise EngineError("ENGINE_BUILD_HASH_MISMATCH")
    if len(payload) > MAX_INPUT_BYTES:
        raise EngineError("INPUT_TOO_LARGE")
    with tempfile.TemporaryDirectory(prefix="boreal-engine-") as temporary:
        directory = Path(temporary)
        (directory / "input.dat").write_bytes(payload)
        command = [str(executable), "input.dat", "output.dat"]
        if policy is not None:
            command.append(policy)
        if os.name == "posix":
            command = [sys.executable, str(ENGINE / "limit_exec.py"), *command]
        with (directory / "stdout.log").open("wb") as stdout, (directory / "stderr.log").open("wb") as stderr:
            try:
                process = subprocess.run(
                    command,
                    cwd=directory,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout,
                    stderr=stderr,
                    timeout=30,
                    check=False,
                    env={**os.environ, "COB_LS_NULLS": "N", "COB_LS_FIXED": "N"},
                )
            except subprocess.TimeoutExpired as exc:
                raise EngineError("ENGINE_TIMEOUT") from exc
            except OSError as exc:
                raise EngineError("ENGINE_EXECUTION_FAILED") from exc
        if process.returncode != 0:
            detail = (directory / "stderr.log").read_bytes()[:2048].decode("utf-8", "replace")
            raise EngineError(f"ENGINE_EXIT_{process.returncode}: {detail}")
        output = directory / "output.dat"
        if not output.is_file() or output.stat().st_size > MAX_OUTPUT_BYTES:
            raise EngineError("ENGINE_OUTPUT_INVALID")
        try:
            return output.read_text(encoding="ascii").splitlines(), info
        except UnicodeError as exc:
            raise EngineError("ENGINE_OUTPUT_ENCODING") from exc


def _money(value: str) -> str:
    """Decimal storage normalization, never policy evaluation."""
    return format(Decimal(value), ".2f")


def calculate(raw: bytes, policy: str = "V1", build_id: str | None = None) -> dict:
    if policy not in {"V1", "V2"}:
        raise EngineError("POLICY_UNSUPPORTED")
    info = build_info(build_id)
    if not info["available"]:
        raise EngineError(info.get("integrity_error", "ENGINE_UNAVAILABLE"))
    result = {
        "status": "quarantined",
        "errors": [],
        "count": 0,
        "control_total": "0.00",
        "engine_build": info["engine_build"],
        "records": [],
        "schema_version": "BOREAL01",
        "payable_total": "0.00",
    }
    if len(raw) > MAX_INPUT_BYTES:
        raise EngineError("INPUT_TOO_LARGE")
    if not raw.endswith(b"\n") or len(raw) < 243 or len(raw) % 81:
        result["errors"] = ["FILE_FRAMING"]
        return result
    if any(raw[index + 80] != 10 for index in range(0, len(raw), 81)):
        result["errors"] = ["FILE_FRAMING"]
        return result
    if any(byte < 32 or byte > 126 for index, byte in enumerate(raw) if index % 81 != 80):
        result["errors"] = ["FILE_ENCODING"]
        return result
    envelope, _ = _run("envelope", raw, build_id=info["engine_build"])
    if len(envelope) != 1:
        raise EngineError("ENGINE_ENVELOPE_PROTOCOL")
    fields = envelope[0].strip().split("|")
    if fields[0] == "ERROR" and len(fields) == 2:
        result["errors"] = [fields[1]]
        return result
    if fields[0] != "OK" or len(fields) != 3:
        raise EngineError("ENGINE_ENVELOPE_PROTOCOL")
    result.update(status="verified", count=int(fields[1]), control_total=_money(fields[2]))
    seen = set()
    for start in range(81, len(raw) - 81, 81 * CHUNK_SIZE):
        block = raw[start : min(start + 81 * CHUNK_SIZE, len(raw) - 81)]
        details = [block[offset : offset + 80] for offset in range(0, len(block), 81)]
        input_lines = []
        for detail in details:
            identity = (detail[1:9].strip(), detail[9:29].strip())
            input_lines.append(detail + (b"Y" if identity in seen else b"N") + b"\n")
            seen.add(identity)
        output, _ = _run("batch", b"".join(input_lines), policy, info["engine_build"])
        if len(output) != len(details):
            raise EngineError("ENGINE_RECORD_COUNT_MISMATCH")
        for offset, (detail, line) in enumerate(zip(details, output, strict=True)):
            parts = line.split("|")
            if len(parts) != 7:
                raise EngineError("ENGINE_RESULT_PROTOCOL")
            reason, payable, unrounded, rounded, rate, debit, credit = [p.strip() for p in parts]
            accepted = reason == "ACCEPTED"
            record = {
                "position": start // 81 + offset + 1,
                "source": detail[1:9].decode().strip(),
                "reference": detail[9:29].decode().strip(),
                "program": detail[29:33].decode(),
                "business_date": detail[33:41].decode(),
                "eligible_cost": _money(detail[41:52].decode()),
                "beneficiary": detail[52:80].decode().strip(),
                "reason": reason,
                "payable": _money(payable) if accepted else None,
                "trace": {
                    "rate": rate if accepted else None,
                    "unrounded": format(Decimal(unrounded), ".4f") if accepted else None,
                    "rounded": _money(rounded) if accepted else None,
                    "cap": "2500.00",
                    "rounding": "HALF_UP",
                    "rule_id": f"CIR-{policy}",
                    "engine_build": info["engine_build"],
                },
                "proposal": {"debit": debit, "credit": credit, "amount": _money(payable)} if accepted else None,
                "raw_hex": detail.hex(),
            }
            if accepted and (debit != "5100" or credit != "2100" or Decimal(payable) <= 0):
                raise EngineError("ENGINE_JOURNAL_PROTOCOL")
            result["records"].append(record)
    totals, _ = _run(
        "aggregate",
        b"".join(
            (_amount_field(record["payable"]) + "\n").encode()
            for record in result["records"]
            if record["reason"] == "ACCEPTED"
        ),
        build_id=info["engine_build"],
    )
    if len(totals) != 1:
        raise EngineError("ENGINE_AGGREGATE_PROTOCOL")
    result["payable_total"] = _money(totals[0].strip())
    return result


def _amount_field(value: str | None) -> str:
    if value is None:
        return "+0000000.00"
    if not isinstance(value, str) or not re.fullmatch(r"-?\d{1,7}\.\d{2}", value):
        raise EngineError("RECONCILIATION_AMOUNT_SYNTAX")
    try:
        return f"{Decimal(value):+011.2f}"
    except InvalidOperation as exc:
        raise EngineError("RECONCILIATION_AMOUNT_SYNTAX") from exc


def reverse(proposal: dict, build_id: str | None = None) -> dict:
    if proposal.get("debit") != "5100" or proposal.get("credit") != "2100":
        raise EngineError("REVERSAL_UNSUPPORTED")
    payload = ("51002100" + _amount_field(proposal["amount"]) + "\n").encode()
    lines, _ = _run("reverse", payload, build_id=build_id)
    if len(lines) != 1 or len(lines[0].split("|")) != 3:
        raise EngineError("ENGINE_REVERSAL_PROTOCOL")
    debit, credit, amount = lines[0].strip().split("|")
    return {"debit": debit, "credit": credit, "amount": _money(amount)}


def aggregate(values: list[str], build_id: str | None = None) -> str:
    """COBOL total over signed per-record amounts, including comparison deltas."""
    payload = "".join(_amount_field(value) + "\n" for value in values).encode()
    lines, _ = _run("aggregate", payload, build_id=build_id)
    if len(lines) != 1:
        raise EngineError("ENGINE_AGGREGATE_PROTOCOL")
    return _money(lines[0].strip())


def reconcile(rows: list[dict], build_id: str | None = None) -> list[dict]:
    results = []
    for start in range(0, len(rows), CHUNK_SIZE):
        chunk = rows[start : start + CHUNK_SIZE]
        lines = []
        for index, row in enumerate(chunk):
            key = (
                str(row.get("source", ""))[:8].ljust(8)
                + str(row["reference"])[:20].ljust(20)
                + str(row.get("settlement_reference", ""))[:20].ljust(20)
            )
            if any(ord(c) < 32 or ord(c) > 126 for c in key):
                raise EngineError("RECONCILIATION_REFERENCE_SYNTAX")
            lines.append(
                f"{index:09d}{key}{'Y' if row.get('duplicate') else 'N'}"
                f"{'Y' if row.get('expected') is not None else 'N'}{_amount_field(row.get('expected'))}"
                f"{'Y' if row.get('received') is not None else 'N'}{_amount_field(row.get('received'))}\n"
            )
        output, _ = _run("reconcile", "".join(lines).encode("ascii"), build_id=build_id)
        if len(output) != len(chunk):
            raise EngineError("ENGINE_RECONCILIATION_COUNT")
        ordered = {}
        for line in output:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) != 5 or not parts[0].isdigit():
                raise EngineError("ENGINE_RECONCILIATION_PROTOCOL")
            index = int(parts[0])
            if index >= len(chunk) or index in ordered:
                raise EngineError("ENGINE_RECONCILIATION_PROTOCOL")
            _, classification, debit, credit, amount = parts
            if classification not in {"MATCH", "AMOUNT_MISMATCH", "DUPLICATE", "MISSING", "UNEXPECTED"}:
                raise EngineError("ENGINE_RECONCILIATION_PROTOCOL")
            ordered[index] = {
                **chunk[index],
                "classification": classification,
                "proposal": {"debit": debit, "credit": credit, "amount": _money(amount)}
                if classification == "MATCH"
                else None,
            }
        results.extend(ordered[index] for index in range(len(chunk)))
    return results


def decode_packed(values: list[bytes], build_id: str | None = None) -> list[dict]:
    """Validate every packed digit/sign nibble in COBOL before numeric use."""
    results = []
    for start in range(0, len(values), CHUNK_SIZE):
        chunk = values[start : start + CHUNK_SIZE]
        if any(len(value) != 5 for value in chunk):
            raise EngineError("PACKED_LENGTH")
        lines, _ = _run("packed", b"".join(value.hex().upper().encode() + b"\n" for value in chunk), build_id=build_id)
        if len(lines) != len(chunk):
            raise EngineError("ENGINE_PACKED_PROTOCOL")
        for line in lines:
            status, value = line.strip().split("|")
            results.append(
                {
                    "valid": status == "OK",
                    "amount": _money(value) if status == "OK" else None,
                    "reason": "PACKED_VALID" if status == "OK" else value,
                }
            )
    return results


def decode_mixed(raw: bytes, build_id: str | None = None) -> bytes:
    """Decode only bounded IBM-037 fields; never transcode packed binary as text.

    Mixed envelope: ASCII H(80)+LF, one or more binary D(73)+LF,
    ASCII T(80)+LF. Original header and trailer are retained for COBOL controls.
    """
    if len(raw) > MAX_INPUT_BYTES or len(raw) < 236 or (len(raw) - 162) % 74:
        raise EngineError("MIXED_FRAMING")
    if raw[80:81] != b"\n" or raw[-1:] != b"\n":
        raise EngineError("MIXED_FRAMING")
    records = [raw[start : start + 73] for start in range(81, len(raw) - 81, 74)]
    if any(raw[start + 73] != 10 for start in range(81, len(raw) - 81, 74)):
        raise EngineError("MIXED_FRAMING")
    decoded = decode_packed([record[40:45] for record in records], build_id)
    ascii_records = []
    for record, amount in zip(records, decoded, strict=True):
        if not amount["valid"]:
            raise EngineError(amount["reason"])
        try:
            text = b"".join(
                record[a:b].decode("cp037").encode("ascii") for a, b in [(0, 8), (8, 28), (28, 32), (32, 40)]
            )
            beneficiary = record[45:73].decode("cp037").encode("ascii")
        except UnicodeError as exc:
            raise EngineError("MIXED_ENCODING") from exc
        ascii_records.append(b"D" + text + _amount_field(amount["amount"]).encode() + beneficiary + b"\n")
    return raw[:81] + b"".join(ascii_records) + raw[-81:]
