# BOREAL build state

## Completed implementation

Initial implementation completed on 2026-10-29. The documented contracts define the engine, backend and interface boundaries. Verification resolved an audit export race, nullable database checks, frozen-record insertion, historical engine retention and a measured posting bottleneck.

Implemented: native GnuCOBOL calculations/control totals/journals/reconciliation; fixed-width ASCII and bounded IBM-037/packed records; PostgreSQL migrations and immutable financial history; separate durable fenced worker; authenticated operator/approver/auditor sessions; approval digests; real pre/post-commit interruptions and recovery; settlements/reversals; replay/V2 comparison; byte inspector; evidence export/independent verification; bilingual light/dark console; local bootstrap, backup and CI configuration.

## Verified commands and evidence

- Native build: warning-free GnuCOBOL 3.2, build 03a9e2a4dafafc43d1a8.
- Full pytest suite: **81 passed**, 158.04 seconds; one documented upstream test-client deprecation warning. See artifacts/tests.xml.
- scripts/acceptance.py: actual HTTP/worker before-commit and after-commit failures recovered with no omitted/duplicate financial effects; latest run 32.612 seconds.
- tests/browser/workflow.mjs: complete English/light and French/dark workflows passed, including real interruption and auditor ZIP download.
- Browser inspect, QA and reflow: overview, other sections, trace tabs and mobile layouts; zero reported axe violations/runtime errors in final checks. Reports and actual screenshots retained.
- scripts/backup_restore.py: restored 13 preserved imports, financial totals, audit and retained binaries; historical replay passed.
- Final evidence: 83 files, independent integrity and native standalone replay passed; artifacts/final-evidence-verification.json.
- Ruff, compileall, TypeScript/Vite production build and Prettier passed. Python formatting preserved identical ASTs. Dependency scans reported zero known advisories.
- **Verified launch command:** .\scripts\start.ps1 -Wsl. The API and supervised worker passed readiness checks at http://127.0.0.1:8000.

## Measured performance

Native medians: 10,000 records in 0.246 seconds; 100,000 in 2.316 seconds. Supervised bridge: 4.638 / 35.284 seconds. Full HTTP-to-approved-ledger: 15.194 / 130.235 seconds, with 9,900 / 99,000 accepted and 100 / 1,000 rejected. Initial 100,000-row timeout is preserved. Migration 004 plus batched atomic writes resolved the profiled lookup/roundtrip bottleneck. Reports include scope, seeds/hashes, flags, versions and memory limitations.

## Runtime and explicit evidence gaps

Windows host: Python 3.13.3, Node 24.18.0, npm 11.16.0, Git 2.54.0. WSL2 Debian: Python 3.12.12, source-built GnuCOBOL 3.2/GCC 10.2.1, PostgreSQL 17.11 in /opt/boreal-tools, isolated cluster /opt/boreal-data on loopback 55432. WSL package repositories returned missing/stale package errors; tools were compiled in an isolated prefix without upgrading the distribution.

Docker is not installed: container build/start and GitHub Actions execution remain unverified. Docker image digests, configuration and archive lifecycle were inspected/tested separately. Manual screen-reader and actual browser-menu zoom assessments remain unverified. Narrowed CSS viewport reflow is verified; it is not presented as manual zoom evidence. Python result processing is bounded by the upload limit, not constant-memory streaming. Mainframe platforms were not executed.

## Delivery status

Native implementation and demonstration are finished. See README.md, DEMO.md and docs/VERIFICATION.md. Credentials remain private in .local/accounts.json; no secrets are tracked or included in public evidence. Next external verification step, when Docker is available: execute python scripts/bootstrap.py from a clean checkout, then repeat the documented tests. An assistive-technology assessment requires a suitable human-operated setup.
