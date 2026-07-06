"""Runtime blast-radius enforcement.

Keeps runtime-level action throttling aligned with the canonical core safety
policy instead of leaving a no-op placeholder that invites inline forks.
"""

from __future__ import annotations

from typing import Any

from runtime.enforcement import BlastRadiusPolicy, allow_action


class BlastRadiusViolation(RuntimeError):
    """Raised when a high-impact action exceeds the configured hourly budget."""


def _max_per_hour(spec: Any) -> int:
    if spec is None:
        return 0
    limits = getattr(spec, "limits", None)
    for source in (spec, limits):
        if source is None:
            continue
        value = getattr(source, "blast_radius_max_per_hour", None)
        if value is None and isinstance(source, dict):
            value = source.get("blast_radius_max_per_hour")
        if value is not None:
            try:
                return max(0, int(value))
            except Exception:
                return 0
    return 0


def enforce_blast_radius(*, spec: Any, tenant_id: str, user_id: str, action: str = "runtime_action", event_log: Any | None = None) -> None:
    max_per_hour = _max_per_hour(spec)
    if max_per_hour <= 0 or event_log is None:
        return

    ok, debug = allow_action(
        policy=BlastRadiusPolicy(max_per_hour=max_per_hour),
        event_log=event_log,
        tenant_id=str(tenant_id),
        action=str(action or "runtime_action"),
    )
    if not ok:
        raise BlastRadiusViolation(str((debug or {}).get("reason") or "blast_radius_exceeded"))
