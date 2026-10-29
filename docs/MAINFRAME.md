# Mainframe portability and interview notes

This project executes GnuCOBOL native Linux binaries and PostgreSQL. **Enterprise COBOL, DB2, CICS, JCL and host security have not been executed or validated.** No decorative host integration is presented as complete.

| Boundary | Current implementation | Real host adaptation to evaluate |
|---|---|---|
| Compiler | GnuCOBOL3.2 free-format, fixed decimals and COMP-3 | Enterprise COBOL dialect, compiler options, LE behaviour, native tests and performance |
| Records | Explicit ASCII80/LF; bounded IBM-037 character spans and packed-decimal fixture | Dataset RECFM/LRECL, codepages, transfer modes, copybook evolution, actual producer controls |
| Storage | PostgreSQL exact NUMERIC, constraints, locking, unique indexes | DB2 DECIMAL, SQLCODE/SQLSTATE, bind packages, locking/isolation and recovery design |
| Transaction manager | Worker chunk + one PostgreSQL commit | CICS syncpoints or DB2 batch units of recovery; resource coordination and restart conventions |
| Scheduling | Durable database jobs + local supervisor | JCL steps, return codes, scheduler dependencies, GDGs and operational restart/checkpoint procedures |
| Identity | Local Argon2 sessions and server roles | Institution identity, RACF/ACF2/Top Secret, dataset/transaction permissions, audit and segregation of duties |
| Evidence | Local reproducible fixtures and chain checkpoint | Approved artifact retention, trusted external anchors, monitoring, access review and institutional controls |

Do not assume a successfully decoded fixture proves general EBCDIC or packed-decimal compatibility. The supported sign nibbles, widths, offsets and character spans are enumerated and tested. Translate character fields individually; never decode an entire mixed binary record as text.

## Interview talking points

- **Why COBOL owns the rule:** a reviewer can trace raw record bytes through PIC definitions, validation, fixed-decimal multiplication, the one rounding point, cap and journal proposal. HTTP and presentation code cannot silently compute a substitute result.
- **Why 123.45 becomes92.59:** the exact product is92.5875; half-up rounding to cents yields92.59. The cap is applied after rounding. The independently authored Decimal oracle checks random cases and boundaries.
- **Why retries are safe:** journals, state changes, chunk receipts and audit commit together. Before-commit termination produces no effect; after-commit termination leaves a receipt. Unique business keys enforce an additional independent barrier.
- **Why approval binds digests:** authorization covers a specific immutable input/policy/build/result/proposal. A changed proposal is not the object that was approved.
- **Why replay ignores today's state:** current duplicate, settlement and approval state could change historical results. Replay supplies the frozen reference snapshot and recorded engine and never posts.
- **What the hash chain proves:** linkage and exported checkpoints help detect changes. A trusted external anchor would be required to resist privileged rewriting of the entire local chain.
- **What changes in a real engagement:** policy provenance, privacy/security classification, accessibility assessment, host integration, identities, operations, recovery objectives and institution-specific acceptance gates must be established and executed independently.
