CREATE TABLE IF NOT EXISTS scheduled_outbox (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  chat_id INTEGER NOT NULL,
  run_at_ms INTEGER NOT NULL,
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending', -- pending|sent|failed|canceled
  locked_at_ms INTEGER,
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  created_at_ms INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scheduled_outbox_due ON scheduled_outbox(status, run_at_ms);
