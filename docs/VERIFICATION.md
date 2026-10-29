# Verification and accessibility evidence

All results below describe this local synthetic application. They do not establish government authorization, Protected B suitability, certification, comprehensive legal compliance or mainframe compatibility.

## Executed environment

Windows host / WSL2 Debian11; native GnuCOBOL3.2 compiled with GCC10.2.1, `-free -Wall -Wextra -debug`; Python3.12.12; PostgreSQL17.11; Node24.18.0 and npm11.16.0. React19.3.1, Vite8.3.5 and TypeScript7.0.2 were pinned after registry verification. Python and npm lockfiles are delivered. The engine build manifest records source and executable identifiers and exact compiler output. PostgreSQL was compiled in an isolated prefix because the image's package indexes returned404 errors; no embedded database replaced it.

## Financial and durability gates

`artifacts/tests.xml` records the complete suite against compiled COBOL, real PostgreSQL and real worker processes. Independent Decimal expected values and handwritten golden cases cover rounding, caps, limits, rejected costs, dates, controls, corruption and packed nibbles. Integration gates cover role/CSRF checks, separation of duties, immutable history, reversals, idempotency conflicts, duplicate sources, two competing workers, stale ownership, both actual crash boundaries, bounded retry exhaustion, reconciliation, one-cent mismatch, replay/comparison and engine failures. Archive tests cover concurrent build retention, corruption and standalone replay of ASCII/mixed inputs with frozen reference context.

The final expanded suite passed **81 tests in158.04seconds**. `artifacts/tests.xml` contains the complete result. Earlier focused results remain in `artifacts/backend-*.xml` and `engine/test-results.xml`.

`scripts/acceptance.py` executed the authenticated HTTP journey with the live worker. Both injected exits86/87 produced abandoned/recovered attempts and one posted financial effect per accepted reference. It independently checked journal counts, exact payables, replay stability, no comparison postings, unauthorized operations, settlements, linked reversal and ZIP verification. See `artifacts/verification.json`.

`scripts/backup_restore.py` restored a real dump into a fresh database, checked ledger totals and input hashes, verified audit linkage and replayed preserved inputs through binaries extracted from the backup. See `artifacts/backup-restore.json`. The private backup itself remains in `.local/backups/` because it contains authentication data.

## Actual browser and accessibility scope

The **production Vite build** was served by FastAPI. Playwright drove actual local HTTP/worker workflows; no financial API mocks were used.

| Assessment | Evidence | Scope |
|---|---|---|
| Overview across EN/FR, light/dark,1440/1280 widths | `artifacts/accessibility.json` | Eight axe scans, overflow and command-palette keyboard checks |
| Other four sections and trace tabs | `artifacts/browser-quality.json` | Nineteen axe scans, overflow/runtime errors |
| Complete demonstration in English/light and French/dark | `artifacts/browser-workflow.json`, `artifacts/browser-workflow-fr-CA-dark.json` | Upload, unsaved-language preservation, trace/hex, separate approval, crash/recovery, reconciliation/disposition, replay/comparison, auditor download, malformed packed record |
| Reflow and keyboard tabs | `artifacts/browser-reflow.json` |320/390/640CSS-pixel viewports, arrow/End tab operation, French dark trace |
| Visual inspection | `artifacts/screenshots/`, `frontend/test-results/` | Actual captured browser images at desktop/laptop sizes in both languages/themes |

The first overview scan found muted text contrast failures in the light theme. Those colours were darkened and the repeated eight scans passed with zero violations. A stacked-dialog regression left the underlying dialog in the accessibility tree; it was made inert/hidden while retaining its state, then the complete browser flow was rerun. No failing assertions were removed to produce a pass.

Actual keyboard operations include command palette, Escape closing, tab focus, trace-tab arrows and language switching with the current record/tab/file selection preserved. These are scripted browser keyboard checks. **Manual screen-reader testing and browser-menu zoom remain unverified.** An exploratory CSS `body.zoom=2` exercise overflowed because it does not adjust media-query viewport widths; it is not presented as browser-zoom evidence. Narrowed320/390/640CSS-pixel layouts passed independently. Automated passes do not establish comprehensive WCAG conformance.

WCAG2.2AA is the engineering target. Current Canadian ICT transition direction and Digital Standards were consulted; see `docs/REFERENCES.md`. Institutional/contract obligations, accessibility conformance assessment and user research require their own scope and execution.

## Measured performance

| Measurement |10,000 records |100,000 records |
|---|---:|---:|
| Native COBOL pipeline median |0.246s |2.316s |
| Supervised bridge, one observed run |4.638s |35.284s |
| Complete HTTP → approved committed ledger |15.194s |130.235s |
| End-to-end physical records/second |658.15 |767.84 |
| Accepted / rejected in end-to-end input |9,900 /100 |99,000 /1,000 |

Native measurements: one warm-up and three repetitions, including subprocess startup/native file IO, excluding Python transport preparation/parsing and the database. The bridge includes framing, private files and executable hash checks. The complete workflow includes authenticated HTTP import, calculation, independent approval, posting commits and polling; one100-row warm-up and one measured repetition for each size. These are observations on this machine, not forecasts or service-level guarantees.

The initial100,000-row posting attempt exceeded its600-second wait and was preserved in `artifacts/benchmark-initial-failure.json`. Profiling found repeated record-journal lookups without a suitable index and synchronous row-by-row calls. Migration004 added the record/kind index and the worker batches inserts within its existing atomic chunk transaction. An observed10k query used an index-only scan with one matching row. Recovery tests passed again after optimization. A host wall-clock jump also expired one initial lease; fencing recovered it safely. No failed attempt is counted as successful throughput.

`artifacts/engine-benchmarks.json` and `artifacts/e2e-benchmarks.json` include seed/hash, measurement scope, versions/flags, repetitions and hardware information. Python peakRSS for the large bridge measurement was about389,724KiB. The bridge materializes results up to the upload bound; it is not constant-memory streaming. Full process-tree peak memory and detailed latency percentiles are unavailable and are not claimed.

## Static, dependency and delivery checks

Ruff, Python compilation, TypeScript checking and the production frontend build were executed. Python and npm advisory scans found no known vulnerabilities in the installed/pinned set at execution time; reports are under `artifacts/`. Upstream Starlette emitted a test-only deprecation warning for its supported `httpx` adapter; tests still passed. No warning was suppressed.

The [GitHub Actions verification run](https://github.com/MisterFerland/boreal/actions/runs/40896864331) passed on 2026-10-29 for commit `c641b0c5ba81bd27678b64dfa56d196735ed9d92`. A clean Ubuntu 24.04 runner compiled GnuCOBOL 3.2, started PostgreSQL 17.11 as a service container and passed all 81 tests in 29.54 seconds. Ruff, the production frontend build, complete English/light and French/dark browser workflows, independent ZIP verification, standalone native replay and both dependency advisory scans passed. The job retains its generated reports as the `executed-verification` artifact for 14 days. It reported the upstream test-client deprecation warning and GitHub's compatibility warning for actions targeting Node.js 20.

Dockerfile/Compose were reviewed and base-image digests verified through the official registry. Their build/archive initialization logic has real Linux tests. **The application container build and Compose startup remain unverified.** The successful GitHub run used native application processes alongside its PostgreSQL service container. Native WSL startup, real database/process operation and production frontend execution were also verified.
