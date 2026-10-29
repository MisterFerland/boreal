"""Retention checks run on Linux without needing a Docker daemon."""

from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from container_entrypoint import retain_builds


def build_fixture(parent, identity="a" * 20):
    archive = parent / identity
    archive.mkdir(parents=True)
    (archive / "batch").write_bytes(b"fixture-native-binary")
    (archive / "manifest.json").write_text(
        json.dumps(
            {"engine_build": identity, "executables": {"batch": hashlib.sha256(b"fixture-native-binary").hexdigest()}}
        )
    )
    return archive


def test_simultaneous_install_and_historical_retention(tmp_path):
    source, retained = tmp_path / "image", tmp_path / "retained"
    original = build_fixture(source)
    with ProcessPoolExecutor(max_workers=3) as pool:
        tasks = [pool.submit(retain_builds, source, retained) for _ in range(3)]
        for task in tasks:
            task.result(timeout=10)
    assert (retained / original.name / "batch").read_bytes() == b"fixture-native-binary"
    new_source = tmp_path / "next-image"
    updated = build_fixture(new_source, "b" * 20)
    retain_builds(new_source, retained)
    assert (retained / original.name / "batch").exists()
    assert (retained / updated.name / "batch").exists()


def test_retained_binary_corruption_is_not_overwritten(tmp_path):
    source, retained = tmp_path / "image", tmp_path / "retained"
    original = build_fixture(source)
    retain_builds(source, retained)
    binary = retained / original.name / "batch"
    binary.write_bytes(b"corrupt")
    with pytest.raises(RuntimeError, match="integrity"):
        retain_builds(source, retained)
    assert binary.read_bytes() == b"corrupt"


def test_conflicting_same_identity_is_rejected(tmp_path):
    source, retained = tmp_path / "image", tmp_path / "retained"
    original = build_fixture(source)
    retain_builds(source, retained)
    manifest = original / "manifest.json"
    value = json.loads(manifest.read_text())
    value["changed"] = True
    manifest.write_text(json.dumps(value))
    with pytest.raises(RuntimeError, match="conflicts"):
        retain_builds(source, retained)
