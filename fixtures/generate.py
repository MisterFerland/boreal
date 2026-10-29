"""Deterministic synthetic fixtures. Fixture controls use an independent Decimal sum."""

from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parent
SEED = 20261029


def detail(
    reference: str,
    amount: str,
    *,
    source: str = "SYNTH01",
    program: str = "CIR1",
    date: str = "20261029",
    beneficiary: str = "COMMUNITY-001",
) -> bytes:
    result = f"D{source:<8}{reference:<20}{program:<4}{date}{Decimal(amount):+011.2f}{beneficiary:<28}".encode("ascii")
    if len(result) != 80:
        raise ValueError("Fixture field outside ASCII v1 bounds")
    return result


def make_batch(records: list[bytes], name: str = "HAND-CHECK", date: str = "20261029") -> bytes:
    total = sum((Decimal(row[41:52].decode()) for row in records), Decimal("0.00"))
    header = f"HBOREAL01{name:<24}{date}" + " " * 39
    trailer = f"T{len(records):09d}{total:+017.2f}" + " " * 53
    if len(header) != 80 or len(trailer) != 80:
        raise ValueError("Fixture envelope outside v1 bounds")
    return header.encode() + b"\n" + b"".join(record + b"\n" for record in records) + trailer.encode() + b"\n"


def mixed_from_ascii(raw: bytes, sign: str = "C") -> bytes:
    parts = [raw[:81]]
    for start in range(81, len(raw) - 81, 81):
        row = raw[start : start + 80]
        amount = row[41:52].decode()
        nibble = "D" if amount[0] == "-" else sign
        packed = bytes.fromhex(amount[1:].replace(".", "") + nibble)
        parts.append(row[1:41].decode().encode("cp037") + packed + row[52:80].decode().encode("cp037") + b"\n")
    return b"".join(parts) + raw[-81:]


def generate_benchmark(count: int, path: Path) -> dict:
    randomizer = random.Random(SEED)
    total = Decimal("0.00")
    with path.open("wb") as output:
        output.write((f"HBOREAL01{f'BENCH-{count}':<24}20261029" + " " * 39 + "\n").encode())
        for index in range(count):
            cents = randomizer.randrange(1, 600_001)
            amount = Decimal(cents) / 100
            total += amount
            output.write(
                detail(f"BENCH-{index:09d}", str(amount), source="BENCH01", beneficiary=f"SYNTHETIC-{index % 97:03d}")
                + b"\n"
            )
        output.write((f"T{count:09d}{total:+017.2f}" + " " * 53 + "\n").encode())
    return {
        "count": count,
        "seed": SEED,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "control_total": str(total),
        "path": path.name,
    }


def generate() -> None:
    anchors = [detail("ANCHOR-12345", "123.45"), detail("ANCHOR-002", "0.02"), detail("ANCHOR-CAP", "4000.00")]
    hand = make_batch(anchors)
    (ROOT / "hand-check.dat").write_bytes(hand)
    (ROOT / "review.dat").write_bytes(
        make_batch(
            anchors
            + [
                detail("REJECT-ZERO", "0.00"),
                detail("REJECT-NEGATIVE", "-3.00"),
                detail("REJECT-PROGRAM", "120.00", program="BAD1"),
                detail("REJECT-DATE", "100.00", date="20260230"),
                detail("ANCHOR-12345", "123.45"),
            ],
            "REVIEW-WITH-EXCEPTIONS",
        )
    )
    costs = ["123.45", "0.02", "4000.00", "1800.00", "82.50", "3333.33", "3333.34", "0.01", "650.55"]
    demo = [
        detail(f"DEMO-{index:06d}", costs[index % len(costs)], beneficiary=f"COMMUNITY-{index % 12:03d}")
        for index in range(96)
    ]
    (ROOT / "demo.dat").write_bytes(make_batch(demo, "AUTUMN-INFRASTRUCTURE"))
    (ROOT / "pending.dat").write_bytes(
        make_batch(
            [
                detail(
                    f"REVIEW-{index:06d}",
                    costs[index % len(costs)],
                    source="SYNTH02",
                    beneficiary=f"COMMUNITY-{index % 12:03d}",
                )
                for index in range(16)
            ]
            + [detail("REVIEW-INVALID", "0.00", source="SYNTH02")],
            "NORTH-SHORE-REVIEW",
        )
    )
    (ROOT / "mixed-valid.bin").write_bytes(mixed_from_ascii(hand))
    malformed = bytearray(mixed_from_ascii(hand))
    malformed[81 + 40] = 0xFA
    (ROOT / "mixed-invalid-digit.bin").write_bytes(malformed)
    broken_trailer = bytearray(hand)
    broken_trailer[-81 + 26] = ord("9")
    (ROOT / "bad-trailer.dat").write_bytes(broken_trailer)
    (ROOT / "truncated.dat").write_bytes(hand[:-9])
    (ROOT / "settlement.csv").write_text(
        "settlement_reference,source,reference,amount\n"
        "SET-000001,SYNTH01,DEMO-000000,92.59\n"
        "SET-000002,SYNTH01,DEMO-000001,0.03\n"
        "SET-000003,SYNTH01,DEMO-000002,2500.00\n"
        "SET-000003,SYNTH01,DEMO-000002,2500.00\n"
        "SET-UNKNOWN,SYNTH01,NOT-AN-OBLIGATION,12.00\n",
        encoding="utf-8",
        newline="\n",
    )
    metadata = {
        f"COMMUNITY-{index:03d}": {"en-CA": en, "fr-CA": fr}
        for index, (en, fr) in enumerate(
            [
                ("North Shore", "Côte-Nord"),
                ("Riverbend", "Méandre"),
                ("Cedar Valley", "Vallée des Cèdres"),
                ("Lakeview", "Vue-du-Lac"),
                ("Northern Lights", "Aurore boréale"),
                ("Maple Ridge", "Crête des Érables"),
                ("Harbour Point", "Pointe-du-Port"),
                ("Willow Creek", "Ruisseau des Saules"),
                ("Clearwater", "Eau-Claire"),
                ("Pine Crossing", "Traverse des Pins"),
                ("Meadow Brook", "Ruisseau des Prés"),
                ("Sunrise", "Aube"),
            ]
        )
    }
    (ROOT / "beneficiaries.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (ROOT / "golden.json").write_text(
        json.dumps(
            {
                "policy": "V1",
                "expected": [
                    {"cost": "123.45", "payable": "92.59"},
                    {"cost": "0.02", "payable": "0.02"},
                    {"cost": "4000.00", "payable": "2500.00"},
                    {"cost": "0.01", "payable": "0.01"},
                    {"cost": "0.06", "payable": "0.05"},
                    {"cost": "3333.32", "payable": "2499.99"},
                    {"cost": "3333.33", "payable": "2500.00"},
                    {"cost": "9999999.99", "payable": "2500.00"},
                ],
                "anchor_total": "2592.61",
            },
            indent=2,
        )
        + "\n",
        newline="\n",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", type=int, choices=[10000, 100000])
    args = parser.parse_args()
    if args.benchmark:
        print(json.dumps(generate_benchmark(args.benchmark, ROOT / f"benchmark-{args.benchmark}.dat"), indent=2))
    else:
        generate()
        print("Generated deterministic synthetic fixtures.")
