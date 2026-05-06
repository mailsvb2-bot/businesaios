from __future__ import annotations

from dataclasses import dataclass


_NEUTRAL_MODES = {"queued", "accepted", "noop", "configured_noop"}


@dataclass(frozen=True)
class DeliveryOutcomeSignal:
    measurable: bool
    ok: bool
    blocked: bool
    mode: str
    reason: str


def classify_delivery_outcome_signal(*, ok: bool, meta: dict | None = None) -> DeliveryOutcomeSignal:
    payload = dict(meta or {})
    mode = str(payload.get("mode") or "").strip().lower()
    reason = str(payload.get("reason") or "").strip().lower()
    blocked = reason == "blocked"

    if mode in _NEUTRAL_MODES:
        return DeliveryOutcomeSignal(
            measurable=False,
            ok=bool(ok),
            blocked=blocked,
            mode=mode,
            reason=reason,
        )

    return DeliveryOutcomeSignal(
        measurable=True,
        ok=bool(ok),
        blocked=blocked,
        mode=mode,
        reason=reason,
    )
