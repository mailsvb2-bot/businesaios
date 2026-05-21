-- Canonical BusinessAIOS runtime persistence schema.
-- This file is intentionally explicit and idempotent so production boot checks can
-- prove durable state before any external effect is considered releasable.

CREATE TABLE IF NOT EXISTS schema_migrations (
  migration_id TEXT PRIMARY KEY,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS events (
  event_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  user_id TEXT,
  source TEXT NOT NULL,
  event_type TEXT NOT NULL,
  timestamp_ms BIGINT NOT NULL,
  decision_id TEXT,
  correlation_id TEXT,
  payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_tenant_ts ON events (tenant_id, timestamp_ms DESC);
CREATE INDEX IF NOT EXISTS idx_events_tenant_type_ts ON events (tenant_id, event_type, timestamp_ms DESC);

CREATE TABLE IF NOT EXISTS runtime_outbox (
  outbox_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  claimed_at TIMESTAMPTZ,
  dispatched_at TIMESTAMPTZ,
  verified_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_runtime_outbox_status_created ON runtime_outbox (status, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_runtime_outbox_tenant_status ON runtime_outbox (tenant_id, status);

CREATE TABLE IF NOT EXISTS payment_outbox (
  payment_outbox_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS decision_archive (
  decision_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  correlation_id TEXT,
  payload_json TEXT NOT NULL,
  archived_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS evidence_archive (
  evidence_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  decision_id TEXT,
  payload_json TEXT NOT NULL,
  archived_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS runtime_snapshots (
  snapshot_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  snapshot_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS execution_ledger (
  ledger_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  decision_id TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  ledger_marked BOOLEAN NOT NULL DEFAULT FALSE,
  dispatch_claimed BOOLEAN NOT NULL DEFAULT FALSE,
  handler_dispatched BOOLEAN NOT NULL DEFAULT FALSE,
  effect_verified BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_execution_ledger_tenant_decision ON execution_ledger (tenant_id, decision_id);

CREATE TABLE IF NOT EXISTS recovery_queue (
  recovery_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  ledger_id TEXT NOT NULL,
  required_action TEXT NOT NULL,
  status TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_recovery_queue_status_created ON recovery_queue (status, created_at ASC);

INSERT INTO schema_migrations (migration_id) VALUES
  ('events_v1'),
  ('runtime_outbox_v1'),
  ('decision_archive_v1'),
  ('evidence_archive_v1'),
  ('execution_ledger_v1'),
  ('recovery_queue_v1')
ON CONFLICT (migration_id) DO NOTHING;
