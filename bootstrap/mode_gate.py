from __future__ import annotations
CANON_BOOT_MODE_GATE_FINAL_OWNER = True

CANON_BOOT_WIRING_ONLY = True


"""Run-mode validation and startup summary.

Goal: make runtime behavior predictable and avoid "surprise" background servers.

Hard invariants:
- RUN_MODE=telegram must only start Telegram Long Polling runtime.
- RUN_MODE=evolution must only start evolution worker + health server.
- RUN_MODE=demo must not bind ports.
"""

from runtime.platform.config.env_flags import env_str
from runtime.boot.canonical.env import normalize_env


def _env(name: str, default: str = "") -> str:
    return env_str(name, default).strip()



def validate_run_mode(run_mode: str) -> None:
    rm = (run_mode or "").strip().lower()
    if rm not in {"demo", "telegram", "evolution"}:
        raise SystemExit(f"Unknown RUN_MODE: {run_mode!r}. Expected demo|telegram|evolution")

    # In demo, forbid anything that could bind ports.
    if rm == "demo":
        if _env("EVOLUTION_HEALTH_PORT"):
            raise SystemExit("RUN_MODE=demo must not expose EVOLUTION_HEALTH_PORT")
        if _env("TELEGRAM_HEALTH_PORT"):
            raise SystemExit("RUN_MODE=demo must not expose TELEGRAM_HEALTH_PORT")
        if _env("HEALTH_PORT"):
            raise SystemExit("RUN_MODE=demo must not expose HEALTH_PORT")


def startup_summary(run_mode: str) -> dict:
    """Return a compact, non-sensitive startup summary for logs."""

    app_env = normalize_env(_env("APP_ENV") or _env("ENV", "dev"))
    return {
        "env": app_env.lower(),
        "run_mode": (run_mode or "").strip().lower(),
        "log_level": _env("LOG_LEVEL", "INFO").upper(),
        "marketing": _env("MARKETING_ENABLED", "0"),
        "payments": _env("PAYMENT_PROVIDER", ""),
        "db": "sqlite" if _env("SQLITE_DB_PATH") else ("postgres" if _env("DATABASE_URL") else "unknown"),
        "print_events": _env("PRINT_EVENTS", "0"),
    }
