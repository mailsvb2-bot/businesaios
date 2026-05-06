from __future__ import annotations

"""Payments hardening: reconcile state machine (idempotent).

This is an Engine-level pure layer:
  - consumes payment events / provider status snapshots
  - outputs next actions (capture, grant, notify)
  - guarantees idempotency by stable business keys

Keep it minimal: the actual IO happens in effects_impl.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class PaymentReconcileInput:
    tenant_id: str
    user_id: str
    external_id: str
    event: str | None = None
    provider_status: str | None = None


@dataclass(frozen=True)
class PaymentReconcileDecision:
    action: str  # "noop" | "capture" | "grant" | "retry"
    reason: str
    business_key: str


def business_key(inp: PaymentReconcileInput) -> str:
    return f"{inp.tenant_id}:payment:{inp.external_id}"


def reconcile_decide(inp: PaymentReconcileInput) -> PaymentReconcileDecision:
    # Very conservative: if we see 'succeeded' -> grant
    status = (inp.provider_status or "").lower()
    ev = (inp.event or "").lower()

    if "succeeded" in status or "payment.succeeded" in ev:
        return PaymentReconcileDecision(action="grant", reason="paid", business_key=business_key(inp))

    if "waiting_for_capture" in status or "payment.waiting_for_capture" in ev:
        return PaymentReconcileDecision(action="capture", reason="needs_capture", business_key=business_key(inp))

    if status or ev:
        return PaymentReconcileDecision(action="noop", reason="no_change", business_key=business_key(inp))

    return PaymentReconcileDecision(action="retry", reason="unknown", business_key=business_key(inp))
