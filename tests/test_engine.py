from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import random
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))
from boreal.engine import EngineError, aggregate, build_info, calculate, decode_mixed, decode_packed, reconcile, reverse
from fixtures.generate import detail, make_batch, mixed_from_ascii


def test_real_compiler_available():
    assert build_info()["available"], "Compile engine first: python engine/build.py"
    assert "GnuCOBOL" in build_info()["compiler"]


@pytest.mark.parametrize(
    "cost,payable",
    [
        ("123.45", "92.59"),
        ("0.02", "0.02"),
        ("4000.00", "2500.00"),
        ("0.01", "0.01"),
        ("0.06", "0.05"),
        ("3333.32", "2499.99"),
        ("3333.33", "2500.00"),
        ("3333.34", "2500.00"),
        ("9999999.99", "2500.00"),
    ],
)
def test_hand_calculated_goldens(cost, payable):
    result = calculate(make_batch([detail("GOLDEN", cost)]))
    assert result["status"] == "verified"
    assert result["records"][0]["payable"] == payable
    assert result["payable_total"] == payable
    assert result["records"][0]["proposal"] == {"debit": "5100", "credit": "2100", "amount": payable}


def test_independent_decimal_oracle_across_chunk_boundaries():
    randomizer = random.Random(4711)
    amounts = [Decimal(randomizer.randrange(1, 1_000_000_000)) / 100 for _ in range(1003)]
    raw = make_batch([detail(f"ORACLE-{i}", str(amount)) for i, amount in enumerate(amounts)])
    for policy, rate in [("V1", Decimal(".75")), ("V2", Decimal(".80"))]:
        result = calculate(raw, policy)
        expected = [
            min(Decimal("2500"), (amount * rate).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)) for amount in amounts
        ]
        assert [row["payable"] for row in result["records"]] == [f"{amount:.2f}" for amount in expected]
        assert result["payable_total"] == f"{sum(expected):.2f}"
        assert [row["position"] for row in result["records"]] == list(range(2, 1005))


@pytest.mark.parametrize("cost", ["0.00", "-0.01", "-9999999.99"])
def test_nonpositive_rejected_without_proposal(cost):
    result = calculate(make_batch([detail("BAD-COST", cost)]))
    assert result["status"] == "verified"
    assert result["control_total"] == cost
    assert result["records"][0]["reason"] == "COST_NOT_POSITIVE"
    assert result["records"][0]["payable"] is None
    assert result["records"][0]["proposal"] is None


@pytest.mark.parametrize(
    "date,valid",
    [
        ("20240229", True),
        ("20260229", False),
        ("20261301", False),
        ("20260001", False),
        ("00000101", False),
        ("99991231", True),
    ],
)
def test_business_date(date, valid):
    result = calculate(make_batch([detail("DATE", "1.00", date=date)]))
    assert (result["records"][0]["reason"] == "ACCEPTED") is valid


def test_program_identity_and_duplicate_validation():
    result = calculate(
        make_batch(
            [
                detail("ONE", "1.00"),
                detail("ONE", "2.00"),
                detail("TWO", "3.00", program="NOPE"),
                detail("lowercase", "4.00"),
                detail("", "5.00"),
            ]
        )
    )
    assert [r["reason"] for r in result["records"]] == [
        "ACCEPTED",
        "DUPLICATE_REFERENCE",
        "PROGRAM_UNSUPPORTED",
        "IDENTITY_SYNTAX",
        "IDENTITY_REQUIRED",
    ]
    assert result["control_total"] == "15.00"
    assert result["payable_total"] == "0.75"


def test_duplicate_across_chunks():
    rows = [detail(f"R-{i}", "0.02") for i in range(500)] + [detail("R-0", "0.02")]
    result = calculate(make_batch(rows))
    assert result["records"][-1]["reason"] == "DUPLICATE_REFERENCE"


def test_golden_record_bytes():
    record = detail("ANCHOR-12345", "123.45")
    assert len(record) == 80
    assert record[41:52] == b"+0000123.45"
    assert record[:41] == b"DSYNTH01 ANCHOR-12345        CIR120261029"
    assert calculate(make_batch([record]))["records"][0]["raw_hex"] == record.hex()


@pytest.mark.parametrize(
    "mutation,code",
    [
        (lambda r: r[:-1], "FILE_FRAMING"),
        (lambda r: r.replace(b"\n", b"\r\n"), "FILE_FRAMING"),
        (lambda r: b"X" + r[1:], "HEADER_INVALID"),
        (lambda r: r[: 81 + 41] + b"+000012.345" + r[81 + 52 :], "CONTROL_AMOUNT_SYNTAX"),
        (lambda r: r[: 81 + 41] + b"+10000000.00" + r[81 + 52 :], "FILE_FRAMING"),
        (lambda r: r[:-81] + b"T000000002" + r[-71:], "CONTROL_COUNT_MISMATCH"),
        (lambda r: r[:-81] + r[-81:-55] + b"9" + r[-54:], "CONTROL_TOTAL_MISMATCH"),
        (lambda r: r[:90] + b"\x00" + r[91:], "FILE_ENCODING"),
        (lambda r: r + r[-81:], "DATA_AFTER_TRAILER"),
    ],
)
def test_file_quarantine_before_any_domain_results(mutation, code):
    raw = make_batch([detail("ONE", "123.45")])
    result = calculate(mutation(raw))
    assert result["status"] == "quarantined"
    assert result["errors"] == [code]
    assert result["records"] == []


@pytest.mark.parametrize(
    "sign,amount",
    [("A", "123.45"), ("B", "-123.45"), ("C", "123.45"), ("D", "-123.45"), ("E", "123.45"), ("F", "123.45")],
)
def test_explicit_packed_sign_nibbles(sign, amount):
    assert decode_packed([bytes.fromhex("000012345" + sign)])[0] == {
        "valid": True,
        "amount": amount,
        "reason": "PACKED_VALID",
    }


def test_packed_zero_maximum_corruption_and_truncation():
    result = decode_packed([bytes.fromhex(h) for h in ["000000000C", "999999999C", "F00012345C", "0000123450"]])
    assert result[0]["amount"] == "0.00"
    assert result[1]["amount"] == "9999999.99"
    assert result[2]["reason"] == "PACKED_DIGIT"
    assert result[3]["reason"] == "PACKED_SIGN"
    with pytest.raises(EngineError, match="PACKED_LENGTH"):
        decode_packed([b"\x00\x00"])


def test_mixed_format_character_boundaries_and_calculation():
    raw = make_batch([detail("ONE", "123.45"), detail("NEGATIVE", "-0.02"), detail("MAX", "9999999.99")])
    mixed = mixed_from_ascii(raw, sign="F")
    assert mixed[81:89] == "SYNTH01 ".encode("cp037")
    assert mixed[121:126] == bytes.fromhex("000012345F")
    decoded = decode_mixed(mixed)
    assert decoded == raw
    result = calculate(decoded)
    assert [r["reason"] for r in result["records"]] == ["ACCEPTED", "COST_NOT_POSITIVE", "ACCEPTED"]
    assert result["records"][0]["payable"] == "92.59"
    with pytest.raises(EngineError, match="MIXED_FRAMING"):
        decode_mixed(mixed[:-1])
    damaged = bytearray(mixed)
    damaged[121] = 0xFA
    with pytest.raises(EngineError, match="PACKED_DIGIT"):
        decode_mixed(bytes(damaged))


def test_reconciliation_classifications_and_sort_restore_input_order():
    rows = [
        {"reference": "Z", "expected": "92.59", "received": "92.59", "duplicate": False},
        {"reference": "A", "expected": "0.02", "received": "0.03", "duplicate": False},
        {"reference": "E", "expected": "2.00", "received": "2.00", "duplicate": True},
        {"reference": "B", "expected": "5.00", "received": None, "duplicate": False},
        {"reference": "C", "expected": None, "received": "3.00", "duplicate": False},
    ]
    result = reconcile(rows)
    assert [r["classification"] for r in result] == ["MATCH", "AMOUNT_MISMATCH", "DUPLICATE", "MISSING", "UNEXPECTED"]
    assert result[0]["proposal"] == {"debit": "2100", "credit": "1100", "amount": "92.59"}
    assert all(r["proposal"] is None for r in result[1:])


def test_reversal_constructed_by_engine():
    assert reverse({"debit": "5100", "credit": "2100", "amount": "92.59"}) == {
        "debit": "2100",
        "credit": "5100",
        "amount": "92.59",
    }
    with pytest.raises(EngineError):
        reverse({"debit": "2100", "credit": "1100", "amount": "92.59"})


def test_historical_build_replay_and_v2_do_not_mutate_input():
    raw = make_batch([detail("ONE", "123.45")])
    original = calculate(raw)
    assert calculate(raw, build_id=original["engine_build"]) == original
    assert calculate(raw, "V2")["records"][0]["payable"] == "98.76"
    assert calculate(raw) == original


def test_missing_engine_is_never_success(monkeypatch, tmp_path):
    monkeypatch.setenv("BOREAL_ENGINE_BUILDS", str(tmp_path))
    assert not build_info()["available"]
    with pytest.raises(EngineError, match="ENGINE_UNAVAILABLE"):
        calculate(make_batch([detail("ONE", "123.45")]))


def test_actual_native_exit_is_not_a_successful_result():
    # The bridge accepts syntactically valid zero, but the actual compiled
    # reversal executable rejects it and terminates with exit 65.
    with pytest.raises(EngineError, match="ENGINE_EXIT_65"):
        reverse({"debit": "5100", "credit": "2100", "amount": "0.00"})


def test_comparison_aggregate_in_cobol():
    assert aggregate(["98.76", "-92.59"]) == "6.17"
    assert aggregate([]) == "0.00"
    assert aggregate(["9999999.99"] * 3) == "29999999.97"


def test_corrupted_native_binary_is_unhealthy_and_cannot_calculate(monkeypatch, tmp_path):
    info = build_info()
    shutil.copytree(ROOT / "engine" / "builds" / info["engine_build"], tmp_path / info["engine_build"])
    (tmp_path / info["engine_build"] / "batch").write_bytes(b"corrupted executable")
    monkeypatch.setenv("BOREAL_ENGINE_BUILDS", str(tmp_path))
    assert not build_info()["available"]
    assert build_info()["integrity_error"] == "ENGINE_BUILD_HASH_MISMATCH"
    with pytest.raises(EngineError, match="ENGINE_BUILD_HASH_MISMATCH"):
        calculate(make_batch([detail("ONE", "123.45")]))
