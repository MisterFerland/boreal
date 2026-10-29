"""Explicitly remove only the boreal project's synthetic Compose volumes."""

import argparse
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--confirm-synthetic-reset", action="store_true", required=True)
parser.parse_args()
subprocess.run(
    ["docker", "compose", "-p", "boreal", "down", "--volumes", "--remove-orphans"],
    cwd=Path(__file__).resolve().parents[1],
    check=True,
)
print("Removed only Compose project boreal volumes. Run bootstrap to regenerate demonstration data.")
