CREATE TABLE IF NOT EXISTS schema_migrations(version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE users (
 id text PRIMARY KEY, username text NOT NULL UNIQUE, password_hash text NOT NULL,
 role text NOT NULL CHECK(role IN ('operator','approver','auditor')),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE sessions (
 token_hash text PRIMARY KEY, user_id text NOT NULL REFERENCES users(id), csrf text NOT NULL,
 expires_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE login_attempts (id bigserial PRIMARY KEY, identity text NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX login_throttle ON login_attempts(identity,created_at);
CREATE TABLE batches (
 id uuid PRIMARY KEY, name text NOT NULL, status text NOT NULL CHECK(status IN ('queued','calculating','review','quarantined','failed','approved','posting','posted')),
 raw bytea NOT NULL, source_sha256 text NOT NULL UNIQUE, schema_version text NOT NULL DEFAULT 'BOREAL01',
 policy text NOT NULL DEFAULT 'V1' CHECK(policy='V1'), engine_build text,
 submitted_by text NOT NULL REFERENCES users(id), created_at timestamptz NOT NULL DEFAULT now(),
 record_count integer NOT NULL DEFAULT 0 CHECK(record_count>=0), accepted_count integer NOT NULL DEFAULT 0 CHECK(accepted_count>=0), rejected_count integer NOT NULL DEFAULT 0 CHECK(rejected_count>=0),
 control_total numeric(16,2), payable_total numeric(16,2), result_digest text, proposal_digest text,
 reference_snapshot jsonb NOT NULL DEFAULT '{}', errors jsonb NOT NULL DEFAULT '[]', job_id uuid,
 CHECK (accepted_count+rejected_count<=record_count)
);
CREATE TABLE records (
 id uuid PRIMARY KEY, batch_id uuid NOT NULL REFERENCES batches(id), position integer NOT NULL CHECK(position>=1),
 source text NOT NULL, reference text NOT NULL, reason text NOT NULL,
 eligible_cost numeric(16,2), payable numeric(16,2) CHECK(payable>0 AND payable<=2500),
 state text NOT NULL CHECK(state IN ('accepted','rejected','posted','settled','reversed')),
 data jsonb NOT NULL, UNIQUE(batch_id,position)
);
CREATE INDEX records_business_reference ON records(source,reference);
CREATE INDEX records_batch ON records(batch_id,position);
CREATE TABLE approvals (
 batch_id uuid PRIMARY KEY REFERENCES batches(id), approved_by text NOT NULL REFERENCES users(id),
 source_sha256 text NOT NULL, result_digest text NOT NULL, proposal_digest text NOT NULL,
 policy text NOT NULL, engine_build text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE jobs (
 id uuid PRIMARY KEY, batch_id uuid REFERENCES batches(id), kind text NOT NULL CHECK(kind IN ('calculate','post','replay','compare','reconcile')),
 status text NOT NULL CHECK(status IN ('queued','running','retry','succeeded','failed')),
 submitted_by text NOT NULL REFERENCES users(id), payload jsonb NOT NULL DEFAULT '{}', result jsonb,
 completed integer NOT NULL DEFAULT 0, total integer NOT NULL DEFAULT 0, error text,
 fence bigint NOT NULL DEFAULT 0, owner text, lease_until timestamptz,
 attempt_count integer NOT NULL DEFAULT 0, max_attempts integer NOT NULL DEFAULT 5,
 failure_mode text CHECK(failure_mode IN ('before_commit','after_commit')),
 failure_injected boolean NOT NULL DEFAULT false,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX jobs_claim ON jobs(status,created_at);
ALTER TABLE batches ADD CONSTRAINT batches_job_fk FOREIGN KEY(job_id) REFERENCES jobs(id);
CREATE TABLE attempts (
 id bigserial PRIMARY KEY, job_id uuid NOT NULL REFERENCES jobs(id), fence bigint NOT NULL, owner text NOT NULL,
 started_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz, outcome text NOT NULL DEFAULT 'running', error text,
 UNIQUE(job_id,fence)
);
CREATE TABLE receipts (
 job_id uuid NOT NULL REFERENCES jobs(id), chunk integer NOT NULL, record_ids jsonb NOT NULL,
 digest text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(job_id,chunk)
);
CREATE TABLE journals (
 id uuid PRIMARY KEY, kind text NOT NULL CHECK(kind IN ('obligation','settlement','reversal')),
 batch_id uuid NOT NULL REFERENCES batches(id), record_id uuid NOT NULL REFERENCES records(id),
 source text NOT NULL, reference text NOT NULL, amount numeric(16,2) NOT NULL CHECK(amount>0 AND amount<=2500),
 debit text NOT NULL CHECK(debit IN ('5100','2100','1100')), credit text NOT NULL CHECK(credit IN ('5100','2100','1100')),
 currency text NOT NULL DEFAULT 'CAD' CHECK(currency='CAD'),
 reversal_of uuid UNIQUE REFERENCES journals(id), settlement_reference text UNIQUE,
 actor text NOT NULL REFERENCES users(id), reason text,
 created_at timestamptz NOT NULL DEFAULT now(), CHECK(debit<>credit),
 CHECK ((kind='obligation' AND debit='5100' AND credit='2100' AND reversal_of IS NULL AND settlement_reference IS NULL)
  OR (kind='settlement' AND debit='2100' AND credit='1100' AND reversal_of IS NULL AND settlement_reference IS NOT NULL)
  OR (kind='reversal' AND debit='2100' AND credit='5100' AND reversal_of IS NOT NULL AND settlement_reference IS NULL AND length(reason)>0))
);
CREATE UNIQUE INDEX unique_obligation ON journals(source,reference) WHERE kind='obligation';
CREATE UNIQUE INDEX unique_settlement ON journals(source,reference) WHERE kind='settlement';
CREATE INDEX journals_batch ON journals(batch_id,created_at);
CREATE TABLE settlement_imports (
 id uuid PRIMARY KEY, raw bytea NOT NULL, source_sha256 text NOT NULL UNIQUE, name text NOT NULL,
 submitted_by text NOT NULL REFERENCES users(id), job_id uuid NOT NULL REFERENCES jobs(id),
 status text NOT NULL DEFAULT 'queued', created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE reconciliations (
 id uuid PRIMARY KEY, import_id uuid NOT NULL REFERENCES settlement_imports(id), position integer NOT NULL,
 source text NOT NULL, reference text NOT NULL, settlement_reference text,
 record_id uuid REFERENCES records(id), expected numeric(16,2), received numeric(16,2),
 classification text NOT NULL CHECK(classification IN ('MATCH','AMOUNT_MISMATCH','DUPLICATE','MISSING','UNEXPECTED')),
 data jsonb NOT NULL, state text NOT NULL DEFAULT 'open' CHECK(state IN ('open','accepted','reviewed')),
 disposition text, actor text REFERENCES users(id), created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(import_id,position)
);
CREATE TABLE idempotency (
 actor text NOT NULL REFERENCES users(id), key text NOT NULL, payload_digest text NOT NULL, response jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(actor,key)
);
CREATE TABLE audit (
 sequence bigserial PRIMARY KEY, event jsonb NOT NULL, previous_hash text NOT NULL, hash text NOT NULL UNIQUE,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE worker_health (id text PRIMARY KEY, seen_at timestamptz NOT NULL DEFAULT now(), build text);

CREATE FUNCTION immutable_row() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'BOREAL_IMMUTABLE: posted or frozen history cannot be edited'; END $$;
CREATE TRIGGER journals_immutable BEFORE UPDATE OR DELETE ON journals FOR EACH ROW EXECUTE FUNCTION immutable_row();
CREATE TRIGGER audit_immutable BEFORE UPDATE OR DELETE ON audit FOR EACH ROW EXECUTE FUNCTION immutable_row();
CREATE TRIGGER approvals_immutable BEFORE UPDATE OR DELETE ON approvals FOR EACH ROW EXECUTE FUNCTION immutable_row();
CREATE TRIGGER receipts_immutable BEFORE UPDATE OR DELETE ON receipts FOR EACH ROW EXECUTE FUNCTION immutable_row();

CREATE FUNCTION protect_batch_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (NEW.raw,NEW.source_sha256,NEW.policy,NEW.submitted_by,NEW.schema_version) IS DISTINCT FROM (OLD.raw,OLD.source_sha256,OLD.policy,OLD.submitted_by,OLD.schema_version) THEN
  RAISE EXCEPTION 'BOREAL_IMMUTABLE_INPUT';
 END IF;
 IF OLD.result_digest IS NOT NULL AND
  (NEW.engine_build,NEW.result_digest,NEW.proposal_digest,NEW.reference_snapshot,NEW.control_total,NEW.payable_total,NEW.record_count,NEW.accepted_count,NEW.rejected_count)
  IS DISTINCT FROM (OLD.engine_build,OLD.result_digest,OLD.proposal_digest,OLD.reference_snapshot,OLD.control_total,OLD.payable_total,OLD.record_count,OLD.accepted_count,OLD.rejected_count) THEN
  RAISE EXCEPTION 'BOREAL_IMMUTABLE_RESULT';
 END IF;
 IF NEW.status<>OLD.status AND NOT (
  (OLD.status='queued' AND NEW.status IN ('calculating','failed')) OR
  (OLD.status='calculating' AND NEW.status IN ('review','quarantined','failed')) OR
  (OLD.status='failed' AND NEW.status='calculating' AND OLD.result_digest IS NULL) OR
  (OLD.status='review' AND NEW.status='approved') OR
  (OLD.status='approved' AND NEW.status='posting') OR
  (OLD.status='posting' AND NEW.status='posted')) THEN
  RAISE EXCEPTION 'BOREAL_INVALID_BATCH_TRANSITION: % -> %', OLD.status,NEW.status;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER batch_snapshot BEFORE UPDATE ON batches FOR EACH ROW EXECUTE FUNCTION protect_batch_snapshot();
CREATE FUNCTION protect_record_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (NEW.id,NEW.batch_id,NEW.position,NEW.source,NEW.reference,NEW.reason,NEW.eligible_cost,NEW.payable,NEW.data)
 IS DISTINCT FROM (OLD.id,OLD.batch_id,OLD.position,OLD.source,OLD.reference,OLD.reason,OLD.eligible_cost,OLD.payable,OLD.data) THEN
  RAISE EXCEPTION 'BOREAL_IMMUTABLE_RECORD';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER record_snapshot BEFORE UPDATE ON records FOR EACH ROW EXECUTE FUNCTION protect_record_snapshot();
CREATE TRIGGER records_no_delete BEFORE DELETE ON records FOR EACH ROW EXECUTE FUNCTION immutable_row();
CREATE TRIGGER batches_no_delete BEFORE DELETE ON batches FOR EACH ROW EXECUTE FUNCTION immutable_row();

CREATE FUNCTION check_journal_state() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE rec records; original journals;
BEGIN
 SELECT * INTO rec FROM records WHERE id=NEW.record_id FOR UPDATE;
 IF rec.batch_id<>NEW.batch_id OR rec.source<>NEW.source OR rec.reference<>NEW.reference OR rec.payable<>NEW.amount THEN
  RAISE EXCEPTION 'BOREAL_JOURNAL_SOURCE_MISMATCH';
 END IF;
 IF NEW.kind='obligation' AND (rec.state<>'accepted' OR NOT EXISTS(SELECT 1 FROM approvals WHERE batch_id=NEW.batch_id)) THEN
  RAISE EXCEPTION 'BOREAL_OBLIGATION_NOT_APPROVED';
 ELSIF NEW.kind='settlement' AND rec.state<>'posted' THEN RAISE EXCEPTION 'BOREAL_NOT_SETTLEABLE';
 ELSIF NEW.kind='reversal' THEN
  SELECT * INTO original FROM journals WHERE id=NEW.reversal_of;
  IF rec.state<>'posted' OR original.kind<>'obligation' OR original.record_id<>NEW.record_id OR original.amount<>NEW.amount THEN
   RAISE EXCEPTION 'BOREAL_NOT_REVERSIBLE';
  END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER journals_check BEFORE INSERT ON journals FOR EACH ROW EXECUTE FUNCTION check_journal_state();

CREATE FUNCTION check_approval() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE b batches;
BEGIN
 SELECT * INTO b FROM batches WHERE id=NEW.batch_id FOR UPDATE;
 IF b.status<>'review' OR b.submitted_by=NEW.approved_by OR NOT EXISTS(SELECT 1 FROM users WHERE id=NEW.approved_by AND role='approver') THEN
  RAISE EXCEPTION 'BOREAL_SEPARATION_OF_DUTIES';
 END IF;
 IF (b.source_sha256,b.result_digest,b.proposal_digest,b.policy,b.engine_build)
 IS DISTINCT FROM (NEW.source_sha256,NEW.result_digest,NEW.proposal_digest,NEW.policy,NEW.engine_build) THEN
  RAISE EXCEPTION 'BOREAL_APPROVAL_BINDING_MISMATCH';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER approvals_check BEFORE INSERT ON approvals FOR EACH ROW EXECUTE FUNCTION check_approval();
INSERT INTO schema_migrations(version) VALUES ('001');
