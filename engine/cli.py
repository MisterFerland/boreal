"""Direct CLI: python engine/cli.py calculate fixtures/hand-check.dat."""

from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from boreal.engine import build_info, calculate, decode_mixed, decode_packed

parser = argparse.ArgumentParser(description="BOREAL compiled COBOL CLI")
parser.add_argument("command", choices=["info", "calculate", "mixed", "packed"])
parser.add_argument("input", nargs="?")
parser.add_argument("--policy", choices=["V1", "V2"], default="V1")
parser.add_argument("--build")
args = parser.parse_args()
if args.command == "info":
    result = build_info(args.build)
elif args.command == "packed":
    result = decode_packed([bytes.fromhex(args.input)], args.build)
else:
    raw = Path(args.input).read_bytes()
    if args.command == "mixed":
        raw = decode_mixed(raw, args.build)
    result = calculate(raw, args.policy, args.build)
print(json.dumps(result, ensure_ascii=False, indent=2))
