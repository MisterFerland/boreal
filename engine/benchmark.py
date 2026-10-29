"""Measure actual compiled engine boundary separately from database/API throughput."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))
from boreal.engine import build_info, calculate
from fixtures.generate import generate_benchmark


def measure(raw: bytes, info: dict) -> dict:
    build = ROOT / "engine" / "builds" / info["engine_build"]
    elapsed = 0.0
    accepted = 0
    rejected = 0
    with tempfile.TemporaryDirectory(prefix="boreal-benchmark-") as temporary:
        directory = Path(temporary)
        source = directory / "input.dat"
        output = directory / "output.dat"

        def invoke(program: str, payload: bytes, policy: str | None = None) -> list[str]:
            nonlocal elapsed
            source.write_bytes(payload)
            command = [str(build / program), str(source), str(output)] + ([policy] if policy else [])
            started = time.perf_counter()
            subprocess.run(
                command,
                cwd=directory,
                check=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=30,
            )
            elapsed += time.perf_counter() - started
            return output.read_text().splitlines()

        assert invoke("envelope", raw)[0].startswith("OK|")
        payments = []
        for start in range(81, len(raw) - 81, 81 * 500):
            end = min(start + 81 * 500, len(raw) - 81)
            payload = b"".join(raw[i : i + 80] + b"N\n" for i in range(start, end, 81))
            for row in invoke("batch", payload, "V1"):
                fields = row.split("|")
                if fields[0] == "ACCEPTED":
                    accepted += 1
                    payments.append("+" + fields[1] + "\n")
                else:
                    rejected += 1
        total = invoke("aggregate", "".join(payments).encode())[0].strip()
    return {
        "seconds": elapsed,
        "records_per_second": (accepted + rejected) / elapsed,
        "accepted": accepted,
        "rejected": rejected,
        "total": total,
    }


def main() -> None:
    info = build_info()
    if not info["available"]:
        raise RuntimeError("Compile engine first")
    report = {
        "scope": "Native COBOL envelope, bounded batch and aggregate subprocess time; no database or HTTP",
        "measurement": "perf_counter around subprocess.run; includes process startup and native file I/O; excludes fixture generation, transport preparation and output parsing",
        "engine": info,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count_visible": os.cpu_count(),
        "python": platform.python_version(),
        "cpu_model": next(
            (
                line.split(":", 1)[1].strip()
                for line in Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")
            ),
            "unavailable",
        ),
        "memory_total_kib": next(
            (
                line.split(":", 1)[1].strip()
                for line in Path("/proc/meminfo").read_text().splitlines()
                if line.startswith("MemTotal")
            ),
            "unavailable",
        ),
        "container_allocation": "WSL2 local runtime; host allocation not controlled",
        "warmups": 1,
        "repetitions": 3,
        "datasets": [],
    }
    for count in [10000, 100000]:
        path = ROOT / "fixtures" / f"benchmark-{count}.dat"
        fixture = generate_benchmark(count, path)
        raw = path.read_bytes()
        measure(raw, info)
        runs = [measure(raw, info) for _ in range(3)]
        started = time.perf_counter()
        result = calculate(raw)
        bridge_seconds = time.perf_counter() - started
        assert result["count"] == count and len(result["records"]) == count
        report["datasets"].append(
            {
                **fixture,
                "bytes": len(raw),
                "runs": runs,
                "median_seconds": statistics.median(run["seconds"] for run in runs),
                "median_records_per_second": statistics.median(run["records_per_second"] for run in runs),
                "bridge_inclusive_seconds_one_run": bridge_seconds,
                "bridge_inclusive_records_per_second": count / bridge_seconds,
                "financial_result_sha256": hashlib.sha256(
                    json.dumps(result["records"], sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest(),
            }
        )
        print(f"Measured {count} records; COBOL median {report['datasets'][-1]['median_seconds']:.3f}s", flush=True)
    report["process_peak_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report["spawned_process_peak_rss_kib"] = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    report["memory_observation_limit"] = (
        "ru_maxrss is process-wide high-water data. Child observation includes fork/exec "
        "and Python supervision, not isolated native engine memory. Python materializes "
        "the complete bounded-upload result list and report JSON; only native calculation "
        "calls are chunk-bounded. No constant-memory end-to-end claim is made."
    )
    report["latency_percentiles"] = "Not measured; batch throughput only"
    report["end_to_end_database_api"] = "Separate integration benchmark required; not represented by these numbers"
    destination = ROOT / "artifacts" / "engine-benchmarks.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n")
    print(destination)


if __name__ == "__main__":
    main()
