from __future__ import annotations
CANON_BOOT_HELPERS_FINAL_OWNER = True

CANON_BOOT_WIRING_ONLY = True

"""Small, pure helpers used during boot.

No heavy imports here — env parsing and log emission only.
Extracted from system_builder.py.
"""

from typing import Any

from runtime.events import EventLog
from runtime.boot.canonical.event_emit import emit as _canonical_emit
from runtime.boot.env import env_bool, env_float, env_int, env_str


# ---------------------------------------------------------------------------
# Env helpers (delegating to canonical runtime.boot.env parsers)
# ---------------------------------------------------------------------------

def _env(name: str, default: str | None = None) -> str | None:
    value = env_str(name, "")
    value = value.strip()
    if value:
        return value
    return default


def _env_float(name: str, default: float) -> float:
    return env_float(name, default)


def _env_int(name: str, default: int) -> int:
    return env_int(name, default)


def _env_bool(name: str, default: bool) -> bool:
    return env_bool(name, default)


def _env_csv_tuple(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    """Parse ENV like 'marketing, bulk,analytics' -> ('marketing','bulk','analytics').

    Empty tokens ignored. If ENV missing/blank -> default.
    """
    raw = env_str(name, "").strip()
    if not raw:
        return tuple(default)
    parts: list[str] = []
    for p in raw.split(","):
        s = str(p).strip().lower()
        if s:
            parts.append(s)
    return tuple(parts) if parts else tuple(default)


def _mask(s: str | None, keep: int = 4) -> str:
    if not s:
        return "unset"
    if len(s) <= keep:
        return "*" * len(s)
    return s[:keep] + ("*" * (len(s) - keep))


# ---------------------------------------------------------------------------
# Event log helper (best-effort infra events)
# ---------------------------------------------------------------------------

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
