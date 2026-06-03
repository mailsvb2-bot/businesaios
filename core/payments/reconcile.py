from __future__ import annotations

"""Payment reconciliation (core orchestration).

This module is PURE and contains only orchestration logic.
Provider I/O MUST be passed as an injected port (implemented in runtime effects).
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Protocol
from collections.abc import Iterable

RECONCILE_WINDOW_MIN = 30


class EventStoreLike(Protocol):
    def iter_events(
        self,
        *,
        tenant_id: str,
        start_ms: int = 0,
        end_ms: int | None = None,
        event_type: str | None = None,
    ) -> Iterable[dict[str, Any]]: ...


class LedgerEffectMarkPort(Protocol):
    def mark_effect_completed(self, envelope_id: str) -> None: ...
    def mark_effect_failed(self, envelope_id: str) -> None: ...


class PaymentStatusPort(Protocol):
    def get_payment_status(self, *, external_payment_id: str) -> str: ...


def reconcile_pending_payments(*, now: datetime, event_store: EventStoreLike, tenant_id: str = "default", ledger: LedgerEffectMarkPort, payments: PaymentStatusPort) -> int:
    """Reconcile payments created recently but not finalized.

    Returns number of reconciled records.
    """

    window_start = now - timedelta(minutes=RECONCILE_WINDOW_MIN)
    start_ms = int(window_start.timestamp() * 1000)
    end_ms = int(now.timestamp() * 1000)

    n = 0
    for ev in event_store.iter_events(tenant_id=str(tenant_id), start_ms=start_ms, end_ms=end_ms, event_type="payment_created"):
        payload = ev.get("payload") or {}
        ext_id = payload.get("external_id")
        envelope_id = ev.get("decision_id") or ev.get("envelope_id")
        if not ext_id or not envelope_id:
            continue
        status = str(payments.get_payment_status(external_payment_id=str(ext_id))).lower()
        if status in {"succeeded", "success", "paid"}:
            ledger.mark_effect_completed(str(envelope_id))
            n += 1
        elif status in {"canceled", "cancelled", "failed"}:
            ledger.mark_effect_failed(str(envelope_id))
            n += 1
    return n
