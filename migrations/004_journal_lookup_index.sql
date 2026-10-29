-- Profiling the 100,000-record posting flow exposed repeated record-linked
-- journal lookups in state constraints. Keep these checks indexed as the ledger
-- grows; otherwise one existence check per record becomes quadratic.
CREATE INDEX journals_record_kind ON journals(record_id,kind);
INSERT INTO schema_migrations(version) VALUES ('004');
