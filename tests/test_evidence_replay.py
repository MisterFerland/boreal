"""Standalone reproduction from bundle members, including frozen business context."""

import hashlib
import json
from pathlib import Path
import shutil
import sys
import stat
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]
from boreal import engine
from engine.replay_evidence import canonical, extract_verified_zip, financial, replay
from fixtures.generate import detail, make_batch, mixed_from_ascii


@pytest.mark.parametrize("mixed", [False, True])
def test_extracted_snapshot_replay_restores_permissions_and_reference_context(tmp_path, mixed):
    ascii_raw = make_batch([detail("ONE", "123.45"), detail("CONFLICT", "2.00")])
    raw = mixed_from_ascii(ascii_raw) if mixed else ascii_raw
    result = engine.calculate(ascii_raw)
    build = result["engine_build"]
    records = result["records"]
    records[1].update(reason="BUSINESS_KEY_CONFLICT", payable=None, proposal=None)
    if mixed:
        for row in records:
            start = 81 + (row["position"] - 2) * 74
            row["raw_hex"] = raw[start : start + 73].hex()
    (tmp_path / "input").mkdir()
    (tmp_path / "input" / "original.dat").write_bytes(raw)
    documents = {
        "batch.json": {"schema_version": "BOREAL-MIXED01" if mixed else "BOREAL01", "policy": "V1"},
        "reference-snapshot.json": {"conflicting_positions": [3]},
        "calculation.json": financial(records),
    }
    for name, value in documents.items():
        (tmp_path / name).write_text(canonical(value))
    shutil.copytree(engine._build_directory(build), tmp_path / "engine" / build)
    for name in engine.build_info(build)["executables"]:
        (tmp_path / "engine" / build / name).chmod(0o600)
    manifest = {
        "engine_build": build,
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "financial_result_digest": hashlib.sha256(canonical(financial(records)).encode()).hexdigest(),
        "files": {
            path.relative_to(tmp_path).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in tmp_path.rglob("*")
            if path.is_file()
        },
    }
    (tmp_path / "manifest.json").write_text(canonical(manifest))
    report = replay(tmp_path)
    assert report["verified"]
    assert report["payable_total"] == "92.59"
    assert report["differences"] == []

    # The same complete snapshot can be replayed directly from ZIP without
    # writing extracted native binaries into the user's working directory.
    zipped = tmp_path / "evidence.zip"
    with zipfile.ZipFile(zipped, "w", zipfile.ZIP_DEFLATED) as output:
        for name in list(manifest["files"]) + ["manifest.json"]:
            output.write(tmp_path / name, name)
    zip_report = replay(zipped)
    assert zip_report == report

    # A validly serialized but different frozen context must produce concrete
    # replay differences, even when member checksums were regenerated.
    context = tmp_path / "reference-snapshot.json"
    context.write_text(canonical({"conflicting_positions": []}))
    manifest["files"]["reference-snapshot.json"] = hashlib.sha256(context.read_bytes()).hexdigest()
    (tmp_path / "manifest.json").write_text(canonical(manifest))
    report = replay(tmp_path)
    assert not report["verified"]
    assert report["differences"][0]["position"] == 3


@pytest.mark.parametrize(
    "name",
    [
        "../outside",
        "/absolute",
        "nested/../outside",
        r"nested\outside",
        "C:/outside",
        "./normalized",
        "nested//duplicate",
        ".",
    ],
)
def test_zip_rejects_unsafe_names_before_extraction(tmp_path, name):
    payload = b"never execute or extract"
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(name, payload)
        output.writestr("manifest.json", canonical({"files": {name: hashlib.sha256(payload).hexdigest()}}))
    destination = tmp_path / "extracted"
    destination.mkdir()
    with pytest.raises(ValueError, match="Unsafe"):
        extract_verified_zip(archive, destination)
    assert list(destination.iterdir()) == []


def test_zip_rejects_symlinks_before_extraction(tmp_path):
    archive = tmp_path / "link.zip"
    member = zipfile.ZipInfo("link")
    member.create_system = 3
    member.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(member, b"../outside")
        output.writestr("manifest.json", "{}")
    destination = tmp_path / "extracted"
    destination.mkdir()
    with pytest.raises(ValueError, match="ZIP links"):
        extract_verified_zip(archive, destination)
    assert list(destination.iterdir()) == []


@pytest.mark.parametrize("fault", ["hash", "unlisted", "duplicate"])
def test_zip_rejects_invalid_membership_and_hash_before_extraction(tmp_path, fault):
    archive = tmp_path / "bad.zip"
    manifest = {"files": {"data": hashlib.sha256(b"original").hexdigest()}}
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("data", b"changed" if fault == "hash" else b"original")
        if fault == "unlisted":
            output.writestr("unlisted", b"unknown")
        if fault == "duplicate":
            with pytest.warns(UserWarning, match="Duplicate name"):
                output.writestr("data", b"original")
        output.writestr("manifest.json", json.dumps(manifest))
    destination = tmp_path / "extracted"
    destination.mkdir()
    with pytest.raises(ValueError):
        extract_verified_zip(archive, destination)
    assert list(destination.iterdir()) == []
