# Local threat model and operations

The protected assets are synthetic financial history, source bytes, approvals, account credentials and reproducibility evidence. Adversaries considered: an unauthorized browser, an authenticated user exceeding their role, a corrupted/malicious legacy file, a failed worker and concurrent/retried requests. Host administrators, database superusers, compromised engine binaries plus rewritten manifests, and privileged whole-chain/anchor rewrites are outside the local protection model.

| Control | Implementation/evidence | Limit |
|---|---|---|
| Distinct duties | Authenticated operator/approver/auditor; server role checks and DB self-approval guard; direct API tests | Demo accounts are managed by the local host owner |
| Credentials/sessions | Random bootstrap passwords, Argon2id, opaque hashed session tokens, expiry, login throttling | No external identity provider/MFA in this local demonstration |
| Browser mutations | CSRF header, origin checks, SameSite/HttpOnly cookies, restricted host, CSP | HTTP cookie exception only at loopback |
| Files/processes | Upload limits, strict envelope, numeric validation, allowlisted source retrieval, argv subprocess invocation, private directories, time/output/OS limits | Explicit supported layouts; upload-bounded Python result materialization |
| History | Frozen approvals/results, unique business keys, structural journal balance, DB triggers, runtime privilege restrictions | Schema owners/superusers remain privileged |
| Recovery | Database leases/fences, atomic chunk effects/receipts/audit, real exits86/87 | Not general distributed exactly-once execution |
| Audit | Canonical ordered hash chain + exported checkpoint | Anchor needs independent custody for stronger tamper protection |
| Evidence | ZIP includes only allowlisted sources and report files; no credential/session tables | Private full database backups do include authentication state |
| Network | Loopback HTTP port; no exposed Compose DB port; runtime has no telemetry/fonts/CDNs | Dependencies are downloaded at installation |

Application and worker use `boreal_app`. Schema migration uses `boreal_migration`. The administrator initializes roles and performs private backups. Compose API/worker run as uid10001, with capabilities dropped and no Docker socket. Runtime services do not receive migration passwords. Passwords are kept in `.env` / `.local/` (Git ignored), not printed in logs or evidence. Protect those files with the host account's filesystem permissions; WSL on a Windows-mounted workspace inherits host ACL behaviour.

Failure injection is available only with `BOREAL_DEMO=1`. The controls cause the worker to exit during an actual PostgreSQL posting transaction or immediately after commit. Compose restart policy or the local supervisor starts a new process; the durable claim expires and is recovered. Normal operation sets `BOREAL_DEMO=0`, rejecting those controls.

Structured job logs include job IDs and fences. HTTP responses carry correlation IDs. Readiness checks actual engine availability and recent durable worker heartbeat; liveness checks API process availability. Progress and attempt histories are read from PostgreSQL after reconnecting.

No CSV export of user-provided cell text is offered; the evidence export is JSON/binary ZIP, avoiding spreadsheet formula execution. Source identifiers remain escaped React text. Uploaded filenames are labels only, never filesystem paths.

## Recovery runbook

1. Inspect the job's error and attempt history; distinguish engine, file, conflict and ownership failures.
2. Restore the original recorded engine build if unavailable; never replace a financial result with a Python calculation.
3. A crashed worker is restarted by the supervisor. Wait for lease expiry; receipts identify completed chunks.
4. If its automatic budget is exhausted, an authorized user explicitly retries. Review cannot silently alter frozen input; submit a new input for changed content.
5. Business-key conflicts require review; a new idempotency key does not authorize a duplicate payment.
6. Corrections use an authorized linked reversal only while an obligation is unsettled and unreversed.

`scripts/backup_restore.py` saves a private database dump and all referenced engine builds, restores into a uniquely named database, verifies financial totals and source hashes, extracts retained binaries, replays a historical batch and verifies audit chaining. It removes only its own temporary database. See `artifacts/backup-restore.json` for the executed result.
