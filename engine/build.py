"""Compile and retain a content-addressed, native GnuCOBOL engine build."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
FLAGS = ["-free", "-Wall", "-Wextra", "-debug", "-I", str(ROOT / "copybooks")]
PROGRAMS = {
    "batch": ["batch.cob", "validate-record.cob", "calculate-award.cob", "construct-journal.cob"],
    "envelope": ["verify-envelope.cob"],
    "reconcile": ["reconcile.cob"],
    "packed": ["decode-packed.cob"],
    "aggregate": ["aggregate.cob"],
    "reverse": ["reverse-journal.cob"],
}


def build() -> dict:
    compiler = os.environ.get("COBC", "cobc")
    version = subprocess.check_output([compiler, "-V"], text=True).strip()
    sources = sorted(list((ROOT / "src").glob("*.cob")) + list((ROOT / "copybooks").glob("*.cpy")))
    source_hash = hashlib.sha256()
    for source in sources:
        source_hash.update(source.relative_to(ROOT).as_posix().encode() + b"\0" + source.read_bytes())
    source_digest = source_hash.hexdigest()
    identity = hashlib.sha256((source_digest + version + "-free -Wall -Wextra -debug").encode()).hexdigest()[:20]
    destination = ROOT / "builds" / identity
    # Never overwrite retained executables: debug builds may embed compiler
    # timestamps. Rebuilding unchanged sources reuses the verified archive.
    existing = destination / "manifest.json"
    if existing.is_file():
        manifest = json.loads(existing.read_text())
        if not all(
            (destination / name).is_file() and hashlib.sha256((destination / name).read_bytes()).hexdigest() == digest
            for name, digest in manifest["executables"].items()
        ):
            raise RuntimeError("Retained build integrity failure; preserve it for investigation")
        (ROOT / "build.json").write_text(json.dumps(manifest, indent=2) + "\n")
        return manifest
    destination.mkdir(parents=True, exist_ok=True)
    executable_hashes = {}
    with tempfile.TemporaryDirectory(prefix="boreal-build-") as temporary:
        for program, names in PROGRAMS.items():
            executable = Path(temporary) / program
            subprocess.run(
                [compiler, "-x", *FLAGS, "-o", str(executable), *[str(ROOT / "src" / name) for name in names]],
                check=True,
            )
            shutil.copy2(executable, destination / program)
            executable_hashes[program] = hashlib.sha256(executable.read_bytes()).hexdigest()
    for directory in ["src", "copybooks"]:
        shutil.copytree(ROOT / directory, destination / directory, dirs_exist_ok=True)
    manifest = {
        "engine_build": identity,
        "compiler": version.splitlines()[0],
        "compiler_detail": version,
        "source_hash": source_digest,
        "executable_hash": executable_hashes["batch"],
        "executables": executable_hashes,
        "flags": ["-free", "-Wall", "-Wextra", "-debug"],
        "protocol": "BOREAL01",
        "available": True,
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (ROOT / "build.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
