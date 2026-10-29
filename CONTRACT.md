# BOREAL implementation contract — v1

Local, synthetic CAD demonstrator. No deployment, live citizen data or payment connections.

## Financial boundary and engine

GnuCOBOL alone validates domain records, calculates awards, verifies file control totals, proposes journals and classifies reconciliation. Python only frames/transports, persists, authorizes and coordinates. No financial fallback.
V1: positive eligible cost 0.01..9999999.99, rate 0.75, half-up to cents, cap 2500.00. V2 comparison only: 0.80, same cap. CIR1 program. Dates YYYYMMDD validated by COBOL. Monetary values are decimal strings at JSON boundaries, NUMERIC(16,2) in storage, COMP-3 in COBOL.

ASCII v1: 80 byte records, LF delimiter, final LF required. H = type(1), BOREAL01(8), batch(24), date(8), spaces(39). D = type(1), source(8), reference(20), program(4), date(8), amount(11, sign +/-, 7 integer digits, decimal point, 2 fractional digits), beneficiary identifier(28). T = type(1), count(9 digits), total(17, sign,13 integer digits,decimal point,2 fractional digits),spaces(53). Trailer covers ALL physical details including domain rejections. Bad envelope/amount syntax/control totals quarantine the whole file. Duplicate identities within a file are domain rejections after the first. Original bytes preserved.

The engine boundary comprises engine/, fixtures/, backend/boreal/engine.py, tests/test_engine.py and docs/RECORDS.md. Public Python bridge: EngineError; build_info() -> dict; calculate(raw: bytes, policy='V1') -> dict with status ('verified'|'quarantined'), errors: list[str], count:int, control_total:str, engine_build:str, records:list[dict]. Record keys: position, source, reference, program, business_date, eligible_cost, beneficiary, reason ('ACCEPTED' or stable code), payable (decimal string or null), trace (dict including rate, unrounded, rounded, cap), proposal ({debit:'5100',credit:'2100',amount:str} or null), raw_hex. Result canonical digest is backend-owned. reconcile(rows:list[dict]) -> list[dict]; rows contain reference, expected (str|null), received(str|null), duplicate(bool), settlement_reference; result adds classification ('MATCH','AMOUNT_MISMATCH','DUPLICATE','MISSING','UNEXPECTED') and proposal for MATCH debit2100 credit1100. Bounded invocation, <=500 records per calculation chunk internally; complete envelope control validation before results become approvable. Preserve engine source/build in engine/builds. Document changes to the internal wire protocol.

## Lifecycle / persistence

Import: queued -> calculating -> review | quarantined | failed. Run freezes input, policy V1, build, results and proposal digests. review -> approved -> posting -> posted. Separate approver, no self approval. Posting commits immutable approved proposals, receipts and audit in same transaction. Job: queued -> running -> succeeded | retry | failed. Durable claims, fencing token, bounded retries; before/after-commit real process exits only BOREAL_DEMO=1. Unique obligation(source,reference), settlement(reference), file(sha256), receipt(job,chunk). Reversals only unsettled/unreversed obligations; preserve original. Settlement matches require approver; mismatches never settle.

## HTTP contracts (same origin /api)

Session: POST /auth/login {username,password} -> {user:{id,username,role},csrf}; GET /auth/me same; POST /auth/logout. Cookie session, CSRF header X-CSRF-Token for mutations, Idempotency-Key for job submissions. Roles operator, approver, auditor; all can read, operator imports/calculates, approver approves/posts/settles/reverses, auditor exports. Stable error {detail:{code,message}}.

GET /overview -> {metrics:{calculated,approved,posted,settled,outstanding,exceptions,batches},recent_batches:Batch[],health:{engine,worker,engine_build},activity:Audit[]}.
GET /batches?q=&status=&page=1&page_size=20&sort=created_at -> {items:Batch[],total,page,page_size}.
Batch: {id,name,status,created_at,source_sha256,policy,engine_build,record_count,accepted_count,rejected_count,control_total,payable_total,result_digest,submitted_by,job_id?}.
POST /batches (multipart file) -> Batch. GET /batches/{id} -> Batch + {records:Record[],jobs:Job[],approval?,errors:[]} (records paginated via GET /batches/{id}/records).
POST /batches/{id}/approve {} -> Batch. POST /batches/{id}/post {failure_mode?:'before_commit'|'after_commit'} -> Job.
GET /jobs/{id} -> Job {id,kind,status,completed,total,attempts:[],error?,failure_mode?}. POST /jobs/{id}/retry {} -> Job.
Record = engine record + {id,batch_id,state,journals?:Journal[]}.
GET /records/{id}/trace -> {record:Record,batch:Batch,journals:Journal[],attempts:[],source_url:string}.
GET /ledger?q=&page=&page_size= -> {items:Journal[],total,page,page_size}; Journal {id,kind,source,reference,amount,debit,credit,currency,created_at,reversal_of?,batch_id,record_id}. POST /ledger/{id}/reverse {reason}.
GET /audit?page= -> paginated audit; GET /audit/verify -> {valid,count,head}.
POST /reconciliation (multipart file, CSV settlement_reference,source,reference,amount) -> {id,status}; GET /reconciliation?q=&classification=&page= -> {items:[],total,page,page_size}; row {id,reference,settlement_reference,expected,received,classification,disposition?,actor?}. POST /reconciliation/{id}/accept {}; POST /reconciliation/{id}/disposition {reason}.
POST /batches/{id}/replay {} -> durable Job; POST /batches/{id}/compare {} -> durable Job; GET /jobs/{id} includes result:{same?,original_digest?,replay_digest?,differences:[],v1_total?,v2_total?,delta?} once complete.
GET /batches/{id}/evidence -> ZIP (auditor). GET /engine/source/{build}/{name} allowlist only. GET /health/live; GET /health/ready. GET /fixtures/{name} allowlist. GET /benchmarks -> recorded reports only.

## Interface

frontend/ contains the React/TS/Vite console: five sections, light/dark, en-CA/fr-CA, locally bundled fonts and exact string/BigInt money formatting. Fetch the actual API with credentials; no fake data or successful placeholder actions. Persist language/theme/view and handle empty data gracefully. Login uses generated accounts (no hardcoded passwords). Operator and approver require separate login. API extensions must preserve the documented contracts. Repository delivery includes tests, scripts, containers, documentation and BUILD_STATE.md.
