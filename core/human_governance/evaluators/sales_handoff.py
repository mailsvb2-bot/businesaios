from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.human_governance.contracts_policy import HumanGovernancePolicyContract
from core.human_governance.types import SalesHandoffSignal


def evaluate_sales_handoff(
    *,
    policy: HumanGovernancePolicyContract,
    tenant_id: str,
    subject_id: str,
    model_confidence: float,
    explicit_human_request: bool = False,
    sensitive_context: bool = False,
    pricing_exception: bool = False,
    negative_sentiment: bool = False,
    failed_attempts: int = 0,
    subject_closed: bool = False,
    context: Mapping[str, Any] | None = None,
) -> SalesHandoffSignal | None:
    """Build a governance signal only; perform no notification or execution."""

    tenant = str(tenant_id or "").strip()
    subject = str(subject_id or "").strip()
    if not tenant:
        raise ValueError("tenant_id is required")
    if not subject:
        raise ValueError("subject_id is required")
    classification = policy.evaluate_sales_handoff(
        model_confidence=model_confidence,
        explicit_human_request=explicit_human_request,
        sensitive_context=sensitive_context,
        pricing_exception=pricing_exception,
        negative_sentiment=negative_sentiment,
        failed_attempts=failed_attempts,
        subject_closed=subject_closed,
    )
    if classification is None:
        return None
    reason, risk_level, summary = classification
    return SalesHandoffSignal(
        tenant_id=tenant,
        subject_id=subject,
        reason=reason,
        risk_level=risk_level,
        summary=summary,
        context=dict(context or {}),
    )


__all__ = ["evaluate_sales_handoff"]
