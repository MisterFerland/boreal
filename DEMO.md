# Seven-minute BOREAL demonstration

Prerequisite: bootstrap the local application and have `.local/accounts.json` available privately. Open `http://127.0.0.1:8000`. Use separate browser contexts for operator, approver and auditor. Never display passwords in screenshots or exported evidence.

## 0:00–0:45 — Establish provenance

Sign in as operator. The populated Overview reports persisted approved obligations, outstanding payable, exceptions and recent batches. Point out that calculated, approved, posted and settled are different stages. Read the actual engine build shown in the sidebar. State: “This is an independent portfolio demonstrator using synthetic data and invented policy.”

## 0:45–1:45 — Import and inspect

Open **Batches → Import batch**. Import `fixtures/pending.dat`; an identical reupload returns its original receipt. This fixture contains16 positive instructions and one zero-cost rejection. Inspect source control total, input digest, accepted/rejected counts and original submitter. A domain rejection is different from quarantine: importing `fixtures/bad-trailer.dat` quarantines the whole file.

## 1:45–2:45 — Trace one payment

Open the already-posted `hand-check.dat` batch and select its123.45 instruction. **Trace this payment** shows123.45 eligible cost, exact92.5875 product,92.59 rounded payable, cap2500.00, rule/build and the corresponding proposal. Follow the allowlisted COBOL source link. Select **Source bytes**, highlight the amount field and compare its offsets/PIC definition with original hexadecimal bytes. Switch the dialog into French; the selected record/tab remains open.

## 2:45–3:20 — Mixed binary boundary

Open **Workbench**, inspect `mixed-valid.bin`, then `mixed-invalid-digit.bin`. Explain that character fields alone use IBM-037 and the five packed bytes are validated nibble by nibble. The malformed digit is rejected by compiled COBOL. This is an explicitly bounded format, not a general mainframe compatibility claim.

## 3:20–4:30 — Approve and interrupt

In the separate approver context, open `pending.dat`, review the accepted/rejected disclosure and choose **Approve proposals**. Select **Interrupt after commit**, then **Post approved batch**. The worker really exits; its supervisor restarts it. Observe the abandoned/recovered attempts and final posted status. Existing chunk receipts prevent duplicate financial effects. The automated demonstration also executes the before-commit interruption independently.

If `pending.dat` was already approved during an earlier demonstration, generate/import a new synthetic fixture or run the repeatable browser workflow command below. Do not reset or rewrite posted history to make a demo appear new.

## 4:30–5:20 — Reconcile

Open **Reconciliation**. Inspect the seeded exact92.59 settlement and the one-cent mismatch: expected0.02, received0.03. Only an approver can accept an open exact match. Record a review reason for an exception; the mismatched amount remains an exception and is not marked paid. Duplicate and unexpected references remain visible.

## 5:20–6:20 — Reproduce

Choose a posted batch in **Workbench**. Run **Historical replay**: the digest matches using preserved bytes, frozen policy/reference snapshot and the recorded engine. Run **Compare policy versions**: V1 versus V2, exact per-record differences and aggregate delta. Verify no new ledger entries are created.

## 6:20–7:00 — Export proof

In the auditor context, export the evidence ZIP. Show the manifest, original input, snapshots, sources, executable/build identifiers, journal/control records and audit verification. Verify it independently:

```sh
python scripts/verify_evidence.py artifacts/browser-evidence.zip
python engine/replay_evidence.py artifacts/browser-evidence.zip
```

The verifier checks exported linkage; it cannot protect against an administrator rewriting both a whole chain and its trusted anchor. Close with the measured performance scope and the mainframe portability limitations in `docs/MAINFRAME.md`.

## Repeatable executed equivalent

`node tests/browser/workflow.mjs` creates a unique synthetic batch, performs upload/trace/language-switch/approval/real crash/recovery/reconciliation/replay/comparison/export in the actual browser, and saves `artifacts/browser-workflow.json` plus screenshots. `scripts/acceptance.py` independently exercises both crash boundaries over HTTP. The demonstration evidence reports their actual outcomes; it does not claim a human screen-reader review.
