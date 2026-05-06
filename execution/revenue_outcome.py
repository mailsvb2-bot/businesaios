from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from application.effects.effect_outcome_vocabulary import normalize_outcome_status, outcome_is_verified


CANON_REVENUE_OUTCOME_PROJECTOR = True


def _dictish(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


@dataclass(frozen=True)
class RevenueOutcomeProjector:
    def project(self, *, feedback: Mapping[str, Any], action_result: Any | None = None) -> dict[str, Any]:
        data = _dictish(feedback)
        evidence = _dictish(data.get("evidence"))
        connector_result = _dictish(evidence.get("payload", {})).get("connector_result")
        connector_result = _dictish(connector_result)
        effector = _dictish(_dictish(getattr(action_result, "payload", {})).get("effector")) if action_result is not None else {}
        payload = {**connector_result, **_dictish(effector.get("payload")), **_dictish(evidence.get("effector_evidence"))}
        revenue = float(data.get("revenue") or payload.get("revenue") or payload.get("revenue_amount") or 0.0)
        order_id = str(payload.get("order_id") or payload.get("booking_id") or payload.get("invoice_id") or "").strip()
        invoice_id = str(payload.get("invoice_id") or "").strip()
        payment_id = str(payload.get("payment_id") or payload.get("external_payment_id") or "").strip()
        booking_id = str(payload.get("booking_id") or "").strip()
        outcome_kind = "none"
        if payment_id:
            outcome_kind = "payment"
        elif booking_id:
            outcome_kind = "booking"
        elif invoice_id:
            outcome_kind = "invoice"
        elif order_id:
            outcome_kind = "order"
        evidence_status = normalize_outcome_status(data.get("evidence_status") or data.get("verification_status") or "unverified", verified=data.get("verified"), retryable=data.get("retryable"), default="unverified")
        verified = outcome_is_verified(evidence_status, verified=data.get("verified"), retryable=data.get("retryable")) and outcome_kind != "none"
        return {
            "outcome_kind": outcome_kind,
            "order_id": order_id or None,
            "invoice_id": invoice_id or None,
            "payment_id": payment_id or None,
            "booking_id": booking_id or None,
            "revenue_amount": revenue,
            "verified": verified,
            "evidence_status": evidence_status,
            "closed_loop": bool(verified and revenue > 0),
        }


__all__ = ["CANON_REVENUE_OUTCOME_PROJECTOR", "RevenueOutcomeProjector"]
