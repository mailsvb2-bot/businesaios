"""Private boot-time utility helpers.

Single responsibility: safe env-var parsing and small infra helpers
used only during boot (not importable from application code).
"""
from __future__ import annotations

from typing import Any

from runtime.boot.canonical.event_emit import emit as _canonical_emit
from runtime.events import EventLog
from runtime.platform.config.env_flags import env_bool as _canon_env_bool
from runtime.platform.config.env_flags import env_csv as _canon_env_csv
from runtime.platform.config.env_flags import env_float as _canon_env_float
from runtime.platform.config.env_flags import env_int as _canon_env_int
from runtime.platform.config.env_flags import env_str as _canon_env_str

# ── env parsing ───────────────────────────────────────────────────────────────

def _env(name: str, default: str | None = None) -> str | None:
    v = _canon_env_str(name, "" if default is None else str(default)).strip()
    return v if v else default


def _env_float(name: str, default: float) -> float:
    return float(_canon_env_float(name, float(default)))


def _env_int(name: str, default: int) -> int:
    return int(_canon_env_int(name, int(default)))


def _env_bool(name: str, default: bool) -> bool:
    return bool(_canon_env_bool(name, bool(default)))


def _env_csv_tuple(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    """'marketing, bulk' → ('marketing', 'bulk'). Blank → default."""
    parts = tuple(part.lower() for part in _canon_env_csv(name, ""))
    return parts if parts else tuple(default)


# ── misc helpers ──────────────────────────────────────────────────────────────

def _mask(s: str | None, keep: int = 4) -> str:
    if not s:
        return "unset"
    if len(s) <= keep:
        return "*" * len(s)
    return s[:keep] + ("*" * (len(s) - keep))


def _emit_system_event(event_log: EventLog, event_type: str, payload: dict[str, Any]) -> None:
    """Thin wrapper over the canonical boot event emitter."""
    _canonical_emit(
        event_log,
        event_type,
        source="infra.telegram_outbound",
        user_id="system",
        decision_id="",
        correlation_id="",
        payload=payload if isinstance(payload, dict) else {},
    )
