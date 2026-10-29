-- A PostgreSQL CHECK accepts NULL. IS TRUE explicitly closes that loophole.
ALTER TABLE records DROP CONSTRAINT records_proposal_consistent;
ALTER TABLE records ADD CONSTRAINT records_proposal_consistent CHECK ((
  (reason='ACCEPTED' AND payable IS NOT NULL AND data->>'reason'=reason
   AND data->'proposal'->>'debit'='5100' AND data->'proposal'->>'credit'='2100'
   AND (data->'proposal'->>'amount')::numeric=payable AND state<>'rejected')
  OR (reason<>'ACCEPTED' AND payable IS NULL AND state='rejected' AND data->'proposal'='null'::jsonb)
) IS TRUE);
ALTER TABLE records DROP CONSTRAINT records_identity_consistent;
ALTER TABLE records ADD CONSTRAINT records_identity_consistent CHECK ((
 data->>'source'=source AND data->>'reference'=reference AND (data->>'position')::integer=position
) IS TRUE);

CREATE FUNCTION guard_record_insertion() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE b batches;
BEGIN
 SELECT * INTO b FROM batches WHERE id=NEW.batch_id FOR UPDATE;
 IF b.status<>'calculating' OR b.result_digest IS NOT NULL THEN
  RAISE EXCEPTION 'BOREAL_FROZEN_RECORD_SET';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER records_insert_guard BEFORE INSERT ON records FOR EACH ROW EXECUTE FUNCTION guard_record_insertion();

CREATE FUNCTION check_committed_journal_state() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE s text;
BEGIN
 SELECT state INTO s FROM records WHERE id=NEW.record_id;
 IF (NEW.kind='obligation' AND s NOT IN ('posted','settled','reversed'))
 OR (NEW.kind='settlement' AND s<>'settled') OR (NEW.kind='reversal' AND s<>'reversed') THEN
  RAISE EXCEPTION 'BOREAL_JOURNAL_REQUIRES_ATOMIC_BUSINESS_STATE';
 END IF;
 RETURN NEW;
END $$;
CREATE CONSTRAINT TRIGGER journals_final_state AFTER INSERT ON journals DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION check_committed_journal_state();
INSERT INTO schema_migrations(version) VALUES ('003');
