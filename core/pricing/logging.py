from __future__ import annotations

"""Pricing decision logging helpers.

We keep logging as a tiny primitive to avoid pulling event-store wiring into
pricing policy code.

Event contracts
- pricing_decision_logged
    payload:
      offer_arm, base_price_rub, chosen_price_rub
      policy_id, propensity
      segment (optional)
      candidates (optional) + probs (optional)
      debug (optional small dict)

These events are used for:
- offline training / OPE
- explainability / audits
- stop-loss analysis

IMPORTANT:
- Always pass tenant_id explicitly.
- Keep payload compact (no PII beyond user_id).
"""

import time
from typing import Any, Optional

from core.events.log import EventLog
from core.tenancy.scope import TenantScope


def _now_ms() -> int:
    return int(time.time() * 1000)


def emit_pricing_decision(
    event_store: Any,
    *,
    tenant_id: str,
    user_id: str,
    offer_arm: str,
    base_price_rub: int,
    chosen_price_rub: int,
    policy_id: str,
    propensity: float | None,
    segment: str | None = None,
    candidates: list[int] | None = None,
    probs: dict[str, float] | None = None,
    timestamp_ms: int | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    ts = int(timestamp_ms if timestamp_ms is not None else _now_ms())

    payload: dict[str, Any] = {
        "offer_arm": str(offer_arm),
        "base_price_rub": int(base_price_rub),
        "chosen_price_rub": int(chosen_price_rub),
        "policy_id": str(policy_id),
        "propensity": (float(propensity) if propensity is not None else None),
    }
    if segment:
        payload["segment"] = str(segment)
    if candidates:
        payload["candidates"] = [int(x) for x in candidates]
    if probs:
        # probs are already string-keyed
        payload["probs"] = {str(k): float(v) for k, v in dict(probs).items()}
    if extra:
        # keep it small and JSON-safe
        payload["extra"] = dict(extra)

    log = EventLog(event_store, tenant=TenantScope(str(tenant_id)))
    log.emit(
        event_type="pricing_decision_logged",
        source="pricing",
        user_id=str(user_id),
        payload=payload,
        timestamp_ms=ts,
    )
