"""Retain engine builds alongside durable local state before launching a container service."""

import json
import hashlib
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path


def validate_archive(path):
    manifest = json.loads((path / "manifest.json").read_text())
    if manifest["engine_build"] != path.name or not re.fullmatch(r"[a-f0-9]{20}", path.name):
        raise RuntimeError("Invalid engine archive identity")
    for name, expected in manifest["executables"].items():
        if name not in {"batch", "envelope", "reconcile", "packed", "aggregate", "reverse"}:
            raise RuntimeError("Invalid engine executable name")
        executable = path / name
        if executable.is_symlink() or hashlib.sha256(executable.read_bytes()).hexdigest() != expected:
            raise RuntimeError("Retained engine executable integrity failure")
    if "source_hash" in manifest:
        source_hash = hashlib.sha256()
        for source_file in sorted(list((path / "src").glob("*.cob")) + list((path / "copybooks").glob("*.cpy"))):
            if source_file.is_symlink():
                raise RuntimeError("Retained engine source integrity failure")
            source_hash.update(source_file.relative_to(path).as_posix().encode() + b"\0" + source_file.read_bytes())
        if source_hash.hexdigest() != manifest["source_hash"]:
            raise RuntimeError("Retained engine source integrity failure")
    return manifest


def retain_builds(source, destination):
    # Linux container services share this advisory file lock. Serializing the
    # installation avoids EEXIST/ENOTEMPTY races across API and worker startup.
    import fcntl

    source, destination = Path(source), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / ".install.lock").open("a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        for build in source.iterdir():
            if not build.is_dir():
                continue
            if build.is_symlink():
                raise RuntimeError("Engine archive symlinks are not supported")
            expected = validate_archive(build)
            retained = destination / build.name
            if retained.exists():
                if retained.is_symlink() or validate_archive(retained) != expected:
                    raise RuntimeError(
                        "Retained engine identity conflicts with image; refusing to replace historical build."
                    )
                continue
            temporary = Path(tempfile.mkdtemp(prefix=".install-", dir=destination))
            try:
                shutil.copytree(build, temporary, dirs_exist_ok=True)
                temporary.rename(retained)
            finally:
                if temporary.exists():
                    shutil.rmtree(temporary)


def main():
    retain_builds("/app/engine/builds", os.environ.get("BOREAL_ENGINE_BUILDS", "/app/.local/engine-builds"))
    if len(sys.argv) < 2:
        raise RuntimeError("A container service command is required")
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
