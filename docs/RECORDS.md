# BOREAL legacy records and executable financial boundary

All fixtures are invented synthetic records. This implementation supports exactly the formats below. It is not a general mainframe decoder.

## ASCII BOREAL01

Each physical record is exactly 80 printable ASCII bytes followed by one LF (`0A`), including the final trailer. CRLF, tabs, NUL, non-ASCII, partial records, missing final LF and extra records after the trailer are rejected. Byte offsets below are **zero based**, with end offsets exclusive. Character fields are space padded on the right; source and instruction identifiers permit uppercase ASCII letters, digits, `_`, `-`, and spaces, and cannot be all spaces. Narrow identifiers are separate from bilingual UTF-8 metadata in `fixtures/beneficiaries.json`.

| Record | Offset | Length | Field / syntax |
|---|---:|---:|---|
| Header | 0 | 1 | `H` |
| Header | 1 | 8 | `BOREAL01` |
| Header | 9 | 24 | Nonblank batch name, right padded |
| Header | 33 | 8 | Valid Gregorian `YYYYMMDD` |
| Header | 41 | 39 | Spaces |
| Detail | 0 | 1 | `D` |
| Detail | 1 | 8 | Source system |
| Detail | 9 | 20 | Instruction reference |
| Detail | 29 | 4 | `CIR1` supported |
| Detail | 33 | 8 | Business date `YYYYMMDD` |
| Detail | 41 | 11 | Sign `+`/`-`, seven digits, `.`, two digits |
| Detail | 52 | 28 | Synthetic beneficiary identifier |
| Trailer | 0 | 1 | `T` |
| Trailer | 1 | 9 | Detail count, unsigned zero padded |
| Trailer | 10 | 17 | Sign, thirteen digits, `.`, two digits |
| Trailer | 27 | 53 | Spaces |

For example `+0000123.45` is an exact eligible cost of CAD 123.45. Source positions count physical lines starting with header position 1; the first detail is position 2. Original bytes and input SHA-256 remain the authority.

The trailer amount is the signed sum over **all physical details**, including zero, negative, invalid-program, invalid-date and duplicate instructions. The count has the same scope. Framing, numeric representation and complete envelope controls are verified before any domain result can be approved. Bad controls quarantine the entire import with no calculated records. An intact file can contain individually rejected domain records. The first occurrence of an identity wins within a file; subsequent occurrences are rejected, even across process chunks. Cross-import identity conflicts are separately enforced by PostgreSQL, never silently overwritten.

## Exact policy and supported range

Community Infrastructure Reimbursement / Remboursement des infrastructures communautaires is fictional portfolio policy. Only CAD is supported. A positive cost must be 0.01 through 9,999,999.99 inclusive. V1 computes `min(2500.00, round_half_up(cost * 0.75, 2))`. V2 uses 0.80 and is comparison-only in the application. COBOL `ROUNDED` is applied once after multiplying exact positive fixed-decimal operands. COMP-3 cost is `S9(7)V99`; the four-place intermediate is `9(9)V9(4)`; rounded intermediate is `9(9)V99`; payable is `9(7)V99`. Every financial COMPUTE/ADD has `ON SIZE ERROR`. Maximum cost products fit these intermediates by construction. Signed control and aggregate accumulators are `S9(13)V99`, and the file transport cap is 32 MiB. The application may set a smaller upload bound.

Money crosses HTTP as decimal strings, never floating point. The bridge uses Decimal exclusively to marshal validated monetary representations. PostgreSQL `NUMERIC(16,2)` supplies an independently bounded storage boundary. Python does not evaluate reimbursement, rounding, cap, reconciliation or journal rules. `fixtures/golden.json` and test Decimal oracles are independently authored verification expectations.

COBOL proposes obligation debit 5100 program expense / credit 2100 program payable; settlement debit 2100 / credit 1100 simulated clearing. The reversal executable accepts only a positive original obligation at or below the cap and proposes its compensating accounts. Authorization and unsettled/unreversed eligibility are revalidated transactionally by the application.

## Bounded mixed IBM-037 / packed-decimal fixture

`mixed-valid.bin` contains an ASCII 80-byte header and LF; three 73-byte binary detail records each followed by LF; an ASCII 80-byte trailer and LF. The physical count is derived from exact byte length `(length - 162) / 74`. Delimiters are checked at fixed offsets, **never by splitting binary on LF**. The schema is `engine/copybooks/mixed-v1.cpy`.

| Zero-based offset | Length | Encoding / definition |
|---:|---:|---|
| 0 | 8 | Source, IBM-037 |
| 8 | 20 | Reference, IBM-037 |
| 28 | 4 | Program, IBM-037 |
| 32 | 8 | Business date, IBM-037 |
| 40 | 5 | `PIC S9(7)V99 COMP-3`: nine digit nibbles and one sign nibble |
| 45 | 28 | Beneficiary identifier, IBM-037 |

The bridge translates each character field separately with Python's `cp037` codec. The five packed bytes are sent as ten hexadecimal characters to the compiled `decode-packed.cob`; all nine digit nibbles must be 0–9. Positive sign nibbles A/C/E/F and negative B/D are supported explicitly. Any other sign or digit is rejected before numeric storage. Positive zero decodes syntactically but fails the positive-cost business rule. Negative values decode syntactically and then fail that business rule. `000012345C` means +123.45. `999999999C` is the maximum positive cost. `mixed-invalid-digit.bin` includes an explicit invalid digit nibble. A decoded amount is rendered into ASCII transport and passes through the same COBOL envelope, validation and award programs. The supplied ASCII trailer is preserved, not recomputed in the bridge.

No assumption is made about arbitrary compiler packing conventions, other EBCDIC pages, variable-blocked datasets, RECFM, RDW, national characters, host collating sequences, floating-point data or non-CAD currencies. These were not executed on Enterprise COBOL, DB2, CICS or z/OS.

## Process protocol and error contract

Compile on Linux with `python engine/build.py`, using GnuCOBOL 3.2 and `-free -Wall -Wextra -debug`. The build retains binaries, matching source and copybooks under `engine/builds/<build-id>/`; `engine/build.json` identifies the current build. A build ID hashes source bytes, compiler version and flags. Executable hashes are checked before every invocation. Historical replay can request the recorded build rather than the current build. Backup must include retained build directories and a compatible libcob runtime.

Private working directories contain `input.dat`, `output.dat` and captured logs. Processes are invoked using argument arrays without a shell, with no stdin and a 30-second timeout. Linux supervision sets OS limits before exec: 2 MiB per output/log file, 25 CPU seconds and 256 MiB address space; output-size caps are checked again before parsing. Each calculation invocation has at most 500 detail records. Envelope verification streams the entire input; one aggregate invocation streams calculated payments. No per-row process or concurrent libcob FFI is used.

The internal batch input is the published 80-byte detail plus one duplicate indicator `Y`/`N` and LF. The indicator is a frozen reference lookup supplied by coordination; the COBOL validator owns its rejection decision. Output is `reason|payable|unrounded|rounded|rate|debit|credit`. Rejected numeric outputs are **never exposed as zero payments**: their JSON payable and proposal are null. Reconciliation's fixed record is defined in `reconciliation-v1.cpy`; COBOL SORT orders by source/reference/settlement key and input index before classifying. The bridge restores caller order using the explicit index. No settlement proposal accompanies a mismatch, duplicate, missing or unexpected record.

Exit 0 means a completed protocol operation, which can still report an explicit quarantine or domain rejection. Exit 65 indicates invalid protocol/range; exit 74 indicates I/O failure. FILE STATUS distinguishes `00`, EOF `10`, and failures for every ordinary file; SORT-RETURN is checked for the sort work file. Missing executable, digest mismatch, timeout, nonzero exit, invalid output or count mismatch raises `EngineError` and cannot produce successful calculated financial effects.

Stable reasons: `ACCEPTED`, `RECORD_TYPE`, `IDENTITY_REQUIRED`, `IDENTITY_SYNTAX`, `PROGRAM_UNSUPPORTED`, `DATE_INVALID`, `AMOUNT_SYNTAX`, `AMOUNT_OVERFLOW`, `COST_NOT_POSITIVE`, `DUPLICATE_REFERENCE`, `POLICY_UNSUPPORTED`. Envelope errors: `FILE_FRAMING`, `FILE_ENCODING`, `HEADER_INVALID`, `TRAILER_MISSING`, `DATA_AFTER_TRAILER`, `CONTROL_AMOUNT_SYNTAX`, `CONTROL_OVERFLOW`, `TRAILER_INVALID`, `CONTROL_COUNT_MISMATCH`, `CONTROL_TOTAL_MISMATCH`, `EMPTY_BATCH`, `RECORD_TYPE_INVALID`. Mixed errors: `MIXED_FRAMING`, `MIXED_ENCODING`, `PACKED_LENGTH`, `PACKED_DIGIT`, `PACKED_SIGN`.

## Reproducible direct CLI

```sh
python engine/build.py
python fixtures/generate.py
python engine/cli.py info
python engine/cli.py calculate fixtures/hand-check.dat
python engine/cli.py calculate fixtures/review.dat
python engine/cli.py calculate fixtures/hand-check.dat --policy V2
python engine/cli.py mixed fixtures/mixed-valid.bin
python engine/cli.py packed 000012345C
python engine/cli.py packed F00012345C
python -m pytest tests/test_engine.py -q
python fixtures/generate.py --benchmark 10000
python fixtures/generate.py --benchmark 100000
python engine/benchmark.py
```

The first three anchor amounts produce 92.59, 0.02 and 2500.00, total 2592.61. Tests additionally cover cap edges, half-cent ties, maximum input, zero/negative rejection, leap dates, duplicate identities across chunks, excess precision, out-of-range width, trailer damage, mixed signs and corruption, one-cent reconciliation, archived replay and actual unavailable engines.
