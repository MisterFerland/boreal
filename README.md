# BOREAL

**Native COBOL precision. A transparent financial operations workspace.**

An independent portfolio demonstrator by Yves Ferland. All data, policy and settlements are fictional. No government affiliation, real benefits, citizen data or payment connectivity.

BOREAL imports legacy records, calculates CAD reimbursements in compiled GnuCOBOL, freezes results for independent approval, posts balanced journals through a durable worker, recovers from real process interruptions, reconciles synthetic settlements and exports reproducible evidence. The React console supports English/French, light/dark themes and payment tracing down to the original bytes.

## Start locally

### Docker Compose (portable delivery)

Prerequisites: Docker Engine/Desktop with Compose v2, Python 3.12+, 4 GB available memory, and an internet connection during the first build. No network services are needed after installation.

```powershell
# Windows, from the repository root
python scripts/bootstrap.py
# Equivalent PowerShell launcher
.\scripts\start.ps1
```

```sh
# Linux/macOS
python3 scripts/bootstrap.py
```

Open **http://127.0.0.1:8000**. Read the generated credentials in **.local/accounts.json**; do not publish that file. Use the `operator`, `approver` and `auditor` accounts to demonstrate separation of duties. The bootstrap generates secrets, builds the production frontend and native engine, creates the PostgreSQL roles/schema, generates local accounts, starts API/worker processes and seeds through authenticated API workflows. Repeating it preserves data and credentials.

Docker was not installed in the execution environment. The Compose delivery was inspected but **container execution is unverified**; the same application, compiler, database and production frontend were exercised through native WSL processes below. See [verification evidence](docs/VERIFICATION.md) for the exact scope.

### Verified Windows/WSL runtime

The development machine uses WSL2 Debian, GnuCOBOL 3.2, PostgreSQL 17.11, Python 3.12.12 and Node 24.18.0. Optional native prerequisites: `uv`, a working `cobc` with its shared library, PostgreSQL binaries and Node/npm. `BOREAL_PG_BIN` selects the PostgreSQL `bin` directory; `BOREAL_PG_DATA` selects a project-only cluster location. Defaults are `/opt/boreal-tools/pgsql/bin` and `/opt/boreal-data` in the isolated build distribution. The runtime does not touch other PostgreSQL clusters.

```powershell
# On this prepared machine
.\scripts\start.ps1 -Wsl
```

```sh
# Native Linux/WSL with the above prerequisites installed
sh scripts/local.sh
# Stop API + supervised worker, preserving the database
.venv/bin/python scripts/local_runtime.py --stop
```

If npm is only installed on Windows, build there first: `cd frontend; npm ci; npm run build`; `local.sh` can use the existing production build. The WSL launcher starts the actual API and supervised worker as separate processes, binding HTTP to loopback. Database access uses separate migration/runtime roles. Runtime processes do not receive migration credentials.

## Demonstrate and verify

Follow [DEMO.md](DEMO.md) for the seven-minute walkthrough. [BUILD_STATE.md](BUILD_STATE.md) records completed work and unresolved verification limits.

```sh
# Direct native COBOL, without web services (PATH must contain cobc)
python engine/build.py
python engine/cli.py calculate fixtures/hand-check.dat
python engine/cli.py mixed fixtures/mixed-valid.bin
python engine/cli.py packed 000012345C

# Engine + real PostgreSQL/process integration tests
uv pip sync --python .venv/bin/python backend/requirements-dev.lock
.venv/bin/python scripts/local_runtime.py --exec .venv/bin/python -m pytest -q --junitxml=artifacts/tests.xml

# Live HTTP recovery / reconciliation / replay / evidence gates
.venv/bin/python scripts/acceptance.py

# Private backup, restore to a disposable database and historical replay
.venv/bin/python scripts/local_runtime.py --exec .venv/bin/python scripts/backup_restore.py

# Independent public evidence verifier
python scripts/verify_evidence.py artifacts/acceptance-evidence.zip

# Actual production-browser screenshots and automated accessibility checks
cd frontend
npm ci
npm run build
npx playwright install chromium
cd ..
node tests/browser/inspect.mjs
node tests/browser/workflow.mjs
# Full French / dark workflow (POSIX shell)
BOREAL_BROWSER_LOCALE=fr-CA BOREAL_BROWSER_THEME=dark node tests/browser/workflow.mjs
```

Integration tests create/drop their own uniquely named test database. For CI or another installation, supply `BOREAL_TEST_ADMIN_URL`, `BOREAL_MIGRATION_URL` and `BOREAL_DATABASE_URL`; the administrator needs CREATE DATABASE, and the migrator owns the test schema. They never reset the console database. Native local tests load private administrator credentials from `.local/runtime.json` when needed.

### Reset only synthetic demonstration data

```sh
python scripts/reset.py --confirm-synthetic-reset
python scripts/bootstrap.py
```

This explicitly removes only the `boreal` Compose project's volumes, including its local account file and retained engines. It does not delete the native WSL cluster. Private backups and credentials belong under `.local/` and are excluded from Git and public evidence.

## Policy and financial boundaries

**Community Infrastructure Reimbursement / Remboursement des infrastructures communautaires** is invented portfolio policy. Policy V1 pays `min(2500.00, half_up(eligible_cost × 0.75, 2))`. The eligible input range is **0.01–9,999,999.99 CAD**, with exactly two fractional digits. V2 uses 80% for read-only comparisons; posted history and policy selection remain V1.

| Input | V1 payable | Why |
|---:|---:|---|
| 123.45 | 92.59 | 92.5875 rounded half up |
| 0.02 | 0.02 | 0.015 rounded half up |
| 4000.00 | 2500.00 | 3000.00 capped |
| 0.00 / -1.00 | rejected | Corrections use explicit reversals |

COBOL owns validation, controls, rates, rounding, caps, proposals and reconciliation classifications. Python supervises processes, validates transport and preserves state; PostgreSQL independently enforces storage invariants. The browser only formats decimal strings using exact string/BigInt operations. There is **no Python/JavaScript financial fallback**.

| Journal | Debit | Credit |
|---|---|---|
| Approved obligation | 5100 Program expense | 2100 Program payable |
| Accepted synthetic settlement | 2100 Program payable | 1100 Simulated settlement clearing |
| Authorized reversal | 2100 Program payable | 5100 Program expense |

Each journal stores one positive exact amount shared by its debit/credit legs, making equality structural. Constraints validate account pairs, currency, source, approval and business state. Settled or previously reversed obligations cannot be reversed; unsupported correction states are rejected. Original entries remain unchanged.

## Explore the repository

| Path | Purpose |
|---|---|
| `engine/src/`, `engine/copybooks/` | Reviewable COBOL programs and versioned byte contracts |
| `backend/boreal/` | FastAPI, authentication, durable worker, process boundary |
| `migrations/` | Versioned PostgreSQL constraints, triggers and immutable snapshots |
| `frontend/` | Production React/TypeScript/Vite console, bundled fonts |
| `fixtures/` | Golden inputs, mixed binary examples, synthetic metadata and generators |
| `scripts/` | Bootstrap, seed, verification, backup, performance and operations |
| `tests/` | Independent financial oracle, actual database/process/browser tests |
| `artifacts/` | Actually executed reports; screenshots are local generated artifacts |

Read [architecture and transaction boundaries](docs/ARCHITECTURE.md), [record specifications](docs/RECORDS.md), [security model](docs/SECURITY.md), [verification and accessibility](docs/VERIFICATION.md), [mainframe assessment](docs/MAINFRAME.md), and [French operational summary](docs/REPORT.fr-CA.md).

## Performance and limits

Run `python engine/benchmark.py` for engine measurements and `python scripts/benchmark_e2e.py` through the native environment wrapper for the full HTTP-to-ledger benchmark. Reports specify seed/hash, versions, compiler flags, timing scope, repetitions and available memory observations. Generated 10,000/100,000-record datasets are reproducible; native results must not be presented as end-to-end throughput.

The API caps uploads at 12 MiB; native financial invocations contain at most 500 records. The Python bridge currently materializes the validated result list up to the upload bound. This is **not constant-memory streaming**; the 100,000-record benchmark reports the measured memory cost. UI queries are paginated. Retained native engine archives are required for historical replay and are backed up with the database.

The guarantee demonstrated is **one committed financial effect per business key despite retries**. This is not a claim of unrestricted distributed exactly-once execution. Audit chaining detects changes relative to its retained checkpoint; a privileged rewrite of both the entire chain and trusted anchor is outside the local model.
