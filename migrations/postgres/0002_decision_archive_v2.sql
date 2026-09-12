-- Upgrade the legacy decision_archive created by 0001_runtime_core.sql to the
-- hardened tenant-partitioned envelope schema used by PostgresDecisionArchive.
-- Legacy columns are intentionally preserved so no archived bytes are discarded.

ALTER TABLE decision_archive ADD COLUMN IF NOT EXISTS partition_key TEXT;
ALTER TABLE decision_archive ADD COLUMN IF NOT EXISTS envelope_json TEXT;
ALTER TABLE decision_archive ADD COLUMN IF NOT EXISTS payload_sha256 TEXT;
ALTER TABLE decision_archive ADD COLUMN IF NOT EXISTS signature_kid TEXT;
ALTER TABLE decision_archive ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ;
ALTER TABLE decision_archive ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

UPDATE decision_archive
SET partition_key = COALESCE(
      NULLIF(partition_key, ''),
      'decision_archive:' || CASE
        WHEN LOWER(COALESCE(BTRIM(tenant_id), '')) IN ('', 'default', 'legacy', 'none', 'null') THEN 'global'
        ELSE BTRIM(tenant_id)
      END
    ),
    payload_sha256 = COALESCE(payload_sha256, ''),
    signature_kid = COALESCE(NULLIF(signature_kid, ''), 'legacy-unverified');

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = current_schema() AND table_name = 'decision_archive' AND column_name = 'payload_json'
  ) THEN
    EXECUTE 'UPDATE decision_archive SET envelope_json = COALESCE(NULLIF(envelope_json, ''''), payload_json, ''{}'')';
  ELSE
    UPDATE decision_archive SET envelope_json = COALESCE(NULLIF(envelope_json, ''), '{}');
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = current_schema() AND table_name = 'decision_archive' AND column_name = 'archived_at'
  ) THEN
    EXECUTE 'UPDATE decision_archive SET created_at = COALESCE(created_at, archived_at, NOW()), updated_at = COALESCE(updated_at, archived_at, created_at, NOW())';
  ELSE
    UPDATE decision_archive SET created_at = COALESCE(created_at, NOW()), updated_at = COALESCE(updated_at, created_at, NOW());
  END IF;
END $$;

ALTER TABLE decision_archive ALTER COLUMN partition_key SET NOT NULL;
ALTER TABLE decision_archive ALTER COLUMN envelope_json SET NOT NULL;
ALTER TABLE decision_archive ALTER COLUMN payload_sha256 SET NOT NULL;
ALTER TABLE decision_archive ALTER COLUMN signature_kid SET NOT NULL;
ALTER TABLE decision_archive ALTER COLUMN created_at SET NOT NULL;
ALTER TABLE decision_archive ALTER COLUMN updated_at SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_decision_archive_partition_key ON decision_archive(partition_key);
CREATE INDEX IF NOT EXISTS idx_decision_archive_tenant_id ON decision_archive(tenant_id);
CREATE INDEX IF NOT EXISTS idx_decision_archive_updated_at ON decision_archive(updated_at);

INSERT INTO schema_migrations (migration_id) VALUES ('decision_archive_v2')
ON CONFLICT (migration_id) DO NOTHING;
