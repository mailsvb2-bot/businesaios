-- Canonical runtime-store schema convergence.
-- Runtime adapters must verify this schema, never perform request-time DDL.

ALTER TABLE events ADD COLUMN IF NOT EXISTS append_seq BIGSERIAL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_events_append_seq ON events (append_seq);
CREATE INDEX IF NOT EXISTS idx_events_tenant_append_seq ON events (tenant_id, append_seq);
CREATE INDEX IF NOT EXISTS idx_events_tenant_decision_type ON events (tenant_id, decision_id, event_type);

CREATE TABLE IF NOT EXISTS settings (
  tenant_id TEXT NOT NULL,
  key TEXT NOT NULL,
  value_json TEXT NOT NULL,
  updated_at_ms BIGINT NOT NULL,
  PRIMARY KEY (tenant_id, key)
);

DO $$
DECLARE
  has_runtime_shape BOOLEAN;
  has_legacy_shape BOOLEAN;
BEGIN
  IF to_regclass('payment_outbox') IS NULL THEN
    CREATE TABLE payment_outbox (
      id TEXT PRIMARY KEY,
      dedupe_key TEXT UNIQUE,
      status TEXT NOT NULL,
      payload_json TEXT NOT NULL,
      created_at_ms BIGINT NOT NULL,
      updated_at_ms BIGINT NOT NULL,
      run_after_ms BIGINT NOT NULL,
      attempts INT NOT NULL DEFAULT 0,
      last_error TEXT
    );
  ELSE
    SELECT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = current_schema() AND table_name = 'payment_outbox' AND column_name = 'id'
    ) INTO has_runtime_shape;
    SELECT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = current_schema() AND table_name = 'payment_outbox' AND column_name = 'payment_outbox_id'
    ) INTO has_legacy_shape;

    IF has_legacy_shape AND NOT has_runtime_shape THEN
      ALTER TABLE payment_outbox RENAME TO payment_outbox_legacy_v1;
      CREATE TABLE payment_outbox_v2_new (
        id TEXT PRIMARY KEY,
        dedupe_key TEXT UNIQUE,
        status TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at_ms BIGINT NOT NULL,
        updated_at_ms BIGINT NOT NULL,
        run_after_ms BIGINT NOT NULL,
        attempts INT NOT NULL DEFAULT 0,
        last_error TEXT
      );
      INSERT INTO payment_outbox_v2_new (
        id, dedupe_key, status, payload_json,
        created_at_ms, updated_at_ms, run_after_ms, attempts, last_error
      )
      SELECT
        payment_outbox_id,
        idempotency_key,
        CASE
          WHEN status = 'claimed' THEN 'inflight'
          WHEN status = 'verified' THEN 'delivered'
          ELSE status
        END,
        payload_json,
        (EXTRACT(EPOCH FROM created_at) * 1000)::BIGINT,
        (EXTRACT(EPOCH FROM updated_at) * 1000)::BIGINT,
        (EXTRACT(EPOCH FROM updated_at) * 1000)::BIGINT,
        0,
        NULL
      FROM payment_outbox_legacy_v1
      ON CONFLICT (dedupe_key) DO NOTHING;
      DROP TABLE payment_outbox_legacy_v1;
      ALTER TABLE payment_outbox_v2_new RENAME TO payment_outbox;
    ELSIF NOT has_runtime_shape THEN
      RAISE EXCEPTION 'unsupported payment_outbox schema';
    END IF;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_payment_outbox_status_after
  ON payment_outbox(status, run_after_ms);

CREATE TABLE IF NOT EXISTS payment_terminal (
  external_id TEXT PRIMARY KEY,
  terminal_status TEXT NOT NULL,
  emitted_at_ms BIGINT NOT NULL,
  notification_id TEXT,
  event TEXT
);
CREATE INDEX IF NOT EXISTS idx_payment_terminal_status
  ON payment_terminal(terminal_status);

CREATE TABLE IF NOT EXISTS outbox (
  decision_id TEXT PRIMARY KEY,
  correlation_id TEXT NOT NULL,
  action TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at_ms BIGINT NOT NULL,
  delivered_at_ms BIGINT,
  claimed_at_ms BIGINT,
  next_attempt_at_ms BIGINT,
  retry_count INT NOT NULL DEFAULT 0,
  status TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_outbox_status ON outbox(status, created_at_ms);
CREATE INDEX IF NOT EXISTS idx_outbox_next_attempt ON outbox(status, next_attempt_at_ms);

CREATE TABLE IF NOT EXISTS executed (
  decision_id TEXT PRIMARY KEY,
  executed_at_ms BIGINT NOT NULL,
  policy_id TEXT,
  action TEXT,
  payload_hash TEXT,
  signature TEXT,
  snapshot_id TEXT,
  state_hash TEXT,
  kid TEXT,
  correlation_id TEXT,
  envelope_version INT,
  state_schema_version INT,
  action_schema_version INT
);
CREATE TABLE IF NOT EXISTS executed_chain (
  seq BIGSERIAL PRIMARY KEY,
  decision_id TEXT UNIQUE NOT NULL,
  prev_hash TEXT NOT NULL,
  entry_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS effect_status (
  envelope_id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  updated_at_ms BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_executed_action ON executed(action);
CREATE INDEX IF NOT EXISTS idx_executed_policy ON executed(policy_id);

CREATE TABLE IF NOT EXISTS snapshots (
  snapshot_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  partition_key TEXT NOT NULL,
  canonical_bytes BYTEA NOT NULL,
  content_sha256 TEXT NOT NULL,
  size_bytes BIGINT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_partition_key ON snapshots(partition_key);
CREATE INDEX IF NOT EXISTS idx_snapshots_tenant_id ON snapshots(tenant_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_updated_at ON snapshots(updated_at);

INSERT INTO schema_migrations (migration_id) VALUES
  ('event_store_v2'),
  ('payment_outbox_v2'),
  ('durable_runtime_v2')
ON CONFLICT (migration_id) DO NOTHING;
