-- Storage checks independently reject invalid record/journal lifecycle effects.
ALTER TABLE records ADD CONSTRAINT records_proposal_consistent CHECK (
  (reason='ACCEPTED' AND payable IS NOT NULL AND data->>'reason'=reason
   AND data->'proposal'->>'debit'='5100' AND data->'proposal'->>'credit'='2100'
   AND (data->'proposal'->>'amount')::numeric=payable AND state<>'rejected')
  OR (reason<>'ACCEPTED' AND payable IS NULL AND state='rejected' AND data->'proposal'='null'::jsonb)
);
ALTER TABLE records ADD CONSTRAINT records_identity_consistent CHECK (
 data->>'source'=source AND data->>'reference'=reference AND (data->>'position')::integer=position
);
CREATE FUNCTION protect_record_state() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.state<>OLD.state THEN
  IF OLD.state='accepted' AND NEW.state='posted' THEN
   IF NOT EXISTS(SELECT 1 FROM journals WHERE record_id=NEW.id AND kind='obligation') THEN
    RAISE EXCEPTION 'BOREAL_POSTED_REQUIRES_JOURNAL';
   END IF;
  ELSIF OLD.state='posted' AND NEW.state='settled' THEN
   IF NOT EXISTS(SELECT 1 FROM journals WHERE record_id=NEW.id AND kind='settlement') THEN
    RAISE EXCEPTION 'BOREAL_SETTLED_REQUIRES_JOURNAL';
   END IF;
  ELSIF OLD.state='posted' AND NEW.state='reversed' THEN
   IF NOT EXISTS(SELECT 1 FROM journals WHERE record_id=NEW.id AND kind='reversal') THEN
    RAISE EXCEPTION 'BOREAL_REVERSED_REQUIRES_JOURNAL';
   END IF;
  ELSE RAISE EXCEPTION 'BOREAL_INVALID_RECORD_TRANSITION';
  END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER records_state BEFORE UPDATE ON records FOR EACH ROW EXECUTE FUNCTION protect_record_state();

CREATE FUNCTION protect_settlement_source() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (NEW.raw,NEW.source_sha256,NEW.name,NEW.submitted_by,NEW.job_id)
 IS DISTINCT FROM (OLD.raw,OLD.source_sha256,OLD.name,OLD.submitted_by,OLD.job_id) THEN
  RAISE EXCEPTION 'BOREAL_IMMUTABLE_SETTLEMENT_SOURCE';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER settlement_source BEFORE UPDATE ON settlement_imports FOR EACH ROW EXECUTE FUNCTION protect_settlement_source();

CREATE FUNCTION protect_reconciliation_source() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (NEW.import_id,NEW.position,NEW.source,NEW.reference,NEW.settlement_reference,NEW.record_id,NEW.expected,NEW.received,NEW.classification,NEW.data)
 IS DISTINCT FROM (OLD.import_id,OLD.position,OLD.source,OLD.reference,OLD.settlement_reference,OLD.record_id,OLD.expected,OLD.received,OLD.classification,OLD.data) THEN
  RAISE EXCEPTION 'BOREAL_IMMUTABLE_RECONCILIATION_SOURCE';
 END IF;
 IF OLD.state='accepted' THEN RAISE EXCEPTION 'BOREAL_IMMUTABLE_ACCEPTED_SETTLEMENT'; END IF;
 IF NEW.state='accepted' AND (NEW.classification<>'MATCH' OR NOT EXISTS(
  SELECT 1 FROM journals WHERE record_id=NEW.record_id AND kind='settlement' AND settlement_reference=NEW.settlement_reference)) THEN
  RAISE EXCEPTION 'BOREAL_ACCEPTED_REQUIRES_MATCHED_JOURNAL';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER reconciliation_source BEFORE UPDATE ON reconciliations FOR EACH ROW EXECUTE FUNCTION protect_reconciliation_source();
INSERT INTO schema_migrations(version) VALUES ('002');
