# Autopilot Scheduler

Runs periodically:
- tenants -> connected accounts -> lock -> run engine

Lock key is per (tenant, platform, account).

No new DB is required for audit:
- event_store is the single source of truth
