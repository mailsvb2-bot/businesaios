# Storage policy

This project follows **DECISIONCORE RING SPEC**.

## Production

- **Decision Ledger MUST be PostgreSQL (or equivalent)**.
- This build supports **PostgreSQL** for durable stores when `STORAGE_BACKEND=postgres`.
- Production requires:
  - `APP_ENV=prod` (or `ENV=prod`)
  - `STORAGE_BACKEND=postgres`
  - `POSTGRES_DSN` is set and non-empty

If any of these is missing, the system **fails fast** on startup.

## Development

- SQLite is allowed for local dev and single-node experiments.
- Default is `STORAGE_BACKEND=sqlite` unless `POSTGRES_DSN` is provided.

## Why

SQLite is excellent for iteration, but it is not accepted as a production Decision Ledger
by the Ring Spec. Production must guarantee safe multi-process exactly-once semantics using
PostgreSQL (or an equivalent durable backend).
