from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True


from runtime.platform.config.env_flags import env_str


def storage_self_check() -> None:
    """Production constitution: strict storage must use Postgres.

    This is a *lock* check that must fail fast before any DATA_DIR or sqlite
    paths are resolved.
    """

    # Prefer ENV (legacy) over APP_ENV to match existing constitution tests.
    env = env_str("ENV", env_str("APP_ENV", "dev")).strip().lower()
    # Production constitution is always enforced in APP_ENV=prod.
    if env != "prod":
        return

    backend = env_str("STORAGE_BACKEND", "").strip().lower()
    dsn = env_str("POSTGRES_DSN", "").strip()

    # Canonical rule: in prod strict mode, you must configure Postgres.
    # Accept explicit backend=postgres, or POSTGRES_DSN presence.
    if backend and backend != "postgres":
        raise RuntimeError("PROD_REQUIRES_POSTGRES_STORAGE_BACKEND")
    if not dsn:
        raise RuntimeError("PROD_REQUIRES_POSTGRES_DSN")
