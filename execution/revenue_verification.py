from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping

from execution.action_verification_policy import determine_external_confirmation_mode
from execution.effect_evidence import EffectEvidenceBuilder, EffectEvidenceBundle
from execution.outcome_verifier import OutcomeExpectation, OutcomeVerifier
from execution.revenue_outcome import RevenueOutcomeProjector


CANON_REVENUE_VERIFICATION = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value or "").strip()


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


@dataclass(frozen=True, slots=True)
class RevenueVerificationExpectation:
    min_revenue_amount: float = 0.0
    require_positive_revenue: bool = True
    require_reference: bool = True
    accepted_outcome_kinds: tuple[str, ...] = ("payment", "invoice", "booking", "order")
    external_confirmation_mode: str = "required"

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_revenue_amount": float(self.min_revenue_amount),
            "require_positive_revenue": bool(self.require_positive_revenue),
            "require_reference": bool(self.require_reference),
            "accepted_outcome_kinds": list(self.accepted_outcome_kinds),
            "external_confirmation_mode": self.external_confirmation_mode,
        }


@dataclass(frozen=True, slots=True)
class RevenueVerificationResult:
    verified: bool
    verification_status: str
    reason: str
    revenue_amount: float
    currency: str
    outcome_kind: str
    revenue_reference: str | None
    external_refs: tuple[str, ...] = ()
    projected_outcome: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    expectation: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verified": bool(self.verified),
            "verification_status": self.verification_status,
            "reason": self.reason,
            "revenue_amount": float(self.revenue_amount),
            "currency": self.currency,
            "outcome_kind": self.outcome_kind,
            "revenue_reference": self.revenue_reference,
            "external_refs": list(self.external_refs),
            "projected_outcome": dict(self.projected_outcome),
            "evidence": dict(self.evidence),
            "expectation": dict(self.expectation),
            "metadata": dict(self.metadata),
        }


class RevenueVerification:
    """
    Canonical post-effect revenue verification helper.

    Important:
    - NOT a second verification brain.
    - Outcome evidence semantics remain in execution.outcome_verifier.
    - Revenue shape normalization remains in execution.revenue_outcome.
    - This module only produces a revenue-specific verdict for execution/governance.
    """

    def __init__(
        self,
        *,
        outcome_verifier: OutcomeVerifier | None = None,
        outcome_projector: RevenueOutcomeProjector | None = None,
    ) -> None:
        self._outcome_verifier = outcome_verifier or OutcomeVerifier()
        self._outcome_projector = outcome_projector or RevenueOutcomeProjector()

    def verify(
        self,
        *,
        action_type: str,
        feedback: Mapping[str, Any] | None,
        action_result: Any | None = None,
        expectation: RevenueVerificationExpectation | None = None,
    ) -> RevenueVerificationResult:
        expected = expectation or RevenueVerificationExpectation()
        feedback_payload = _safe_dict(feedback)

        projected = self._outcome_projector.project(
            feedback=feedback_payload,
            action_result=action_result,
        )

        evidence = self._build_evidence(
            action_type=action_type,
            feedback=feedback_payload,
            action_result=action_result,
        )

        verification_expectation = self._build_outcome_expectation(
            action_type=action_type,
            expected=expected,
            evidence=evidence,
        )
        base_verification = self._outcome_verifier.verify(
            expectation=verification_expectation,
            evidence=evidence,
        )

        revenue_amount = max(0.0, _safe_float(projected.get("revenue_amount"), default=0.0))
        outcome_kind = _text(projected.get("outcome_kind") or "none")
        revenue_reference = self._pick_reference(projected)
        currency = self._pick_currency(feedback_payload, action_result)

        failure_reason = self._additional_failure_reason(
            expected=expected,
            revenue_amount=revenue_amount,
            outcome_kind=outcome_kind,
            revenue_reference=revenue_reference,
        )

        if not base_verification.verified:
            verified = False
            verification_status = base_verification.verification_status
            reason = base_verification.reason
        elif failure_reason:
            verified = False
            verification_status = "revenue_unverified"
            reason = failure_reason
        else:
            verified = True
            verification_status = "revenue_verified"
            reason = "verified_revenue_outcome"

        return RevenueVerificationResult(
            verified=verified,
            verification_status=verification_status,
            reason=reason,
            revenue_amount=revenue_amount,
            currency=currency,
            outcome_kind=outcome_kind,
            revenue_reference=revenue_reference,
            external_refs=evidence.external_refs(),
            projected_outcome=projected,
            evidence=evidence.to_dict(),
            expectation=expected.to_dict(),
            metadata={
                "policy_owner": "execution.outcome_verifier",
                "projector_owner": "execution.revenue_outcome",
                "base_verification_status": base_verification.verification_status,
                "base_verification_reason": base_verification.reason,
                "external_matched_records": base_verification.external_matched_records,
                "matched_records": base_verification.matched_records,
                "total_records": base_verification.total_records,
                "has_external_evidence": evidence.has_external_evidence(),
                "has_execution_receipt": any(record.evidence_type == "execution_receipt" for record in evidence.records),
                "evidence_mode": self._evidence_mode(evidence),
            },
        )

    def _build_outcome_expectation(
        self,
        *,
        action_type: str,
        expected: RevenueVerificationExpectation,
        evidence: EffectEvidenceBundle,
    ) -> OutcomeExpectation:
        has_execution_receipt = any(record.evidence_type == "execution_receipt" for record in evidence.records)
        has_external_evidence = evidence.has_external_evidence()

        required_types: list[str] = []
        if has_execution_receipt:
            required_types.append("execution_receipt")
        if has_external_evidence:
            required_types.extend(["connector_snapshot", "router_result"])

        if not required_types:
            required_types = ["router_result"]

        return OutcomeExpectation(
            action_type=_text(action_type),
            required_evidence_types=tuple(dict.fromkeys(required_types)),
            min_successful_records=1,
            external_confirmation_mode=determine_external_confirmation_mode(
                {
                    "action_type": action_type,
                    "external_confirmation_mode": expected.external_confirmation_mode,
                }
            ),
            metadata={
                "owner": "execution.revenue_verification",
                "dynamic_required_types": list(dict.fromkeys(required_types)),
            },
        )

    def _build_evidence(
        self,
        *,
        action_type: str,
        feedback: Mapping[str, Any],
        action_result: Any | None,
    ) -> EffectEvidenceBundle:
        action_payload = _safe_dict(getattr(action_result, "payload", {})) if action_result is not None else {}
        builder = EffectEvidenceBuilder(
            action_type=_text(action_type),
            action_id=_text(
                getattr(action_result, "action_id", None)
                or feedback.get("action_id")
                or action_payload.get("action_id")
            ),
        )

        if action_payload:
            builder.add_execution_receipt(payload=action_payload)

        builder.add_feedback_evidence(feedback=feedback)

        evidence_payload = _safe_dict(feedback.get("evidence"))
        evidence_inner_payload = _safe_dict(evidence_payload.get("payload"))

        connector_result = _safe_dict(
            evidence_inner_payload.get("connector_result")
            or evidence_payload.get("connector_result")
            or evidence_payload.get("connector_snapshot")
        )
        if connector_result:
            builder.add_connector_snapshot(source="connector", payload=connector_result)

        effector_evidence = _safe_dict(evidence_payload.get("effector_evidence"))
        if effector_evidence:
            builder.add_connector_snapshot(source="effector", payload=effector_evidence)

        router_result = _safe_dict(evidence_payload.get("router_result"))
        if router_result:
            builder.add_router_evidence(payload=router_result)

        return builder.build()

    @staticmethod
    def _pick_reference(projected: Mapping[str, Any]) -> str | None:
        for key in ("payment_id", "invoice_id", "booking_id", "order_id"):
            value = _text(projected.get(key))
            if value:
                return value
        return None

    @staticmethod
    def _pick_currency(feedback: Mapping[str, Any], action_result: Any | None) -> str:
        evidence_payload = _safe_dict(feedback.get("evidence"))
        evidence_inner_payload = _safe_dict(evidence_payload.get("payload"))
        connector_result = _safe_dict(evidence_inner_payload.get("connector_result"))
        action_payload = _safe_dict(getattr(action_result, "payload", {})) if action_result is not None else {}

        return (
            _text(feedback.get("currency"))
            or _text(evidence_payload.get("currency"))
            or _text(evidence_inner_payload.get("currency"))
            or _text(connector_result.get("currency"))
            or _text(action_payload.get("currency"))
            or "USD"
        )

    @staticmethod
    def _evidence_mode(evidence: EffectEvidenceBundle) -> str:
        has_execution_receipt = any(record.evidence_type == "execution_receipt" for record in evidence.records)
        has_external = evidence.has_external_evidence()
        if has_execution_receipt and has_external:
            return "execution_and_external"
        if has_external:
            return "external_only"
        if has_execution_receipt:
            return "execution_only"
        return "feedback_only"

    @staticmethod
    def _additional_failure_reason(
        *,
        expected: RevenueVerificationExpectation,
        revenue_amount: float,
        outcome_kind: str,
        revenue_reference: str | None,
    ) -> str | None:
        if outcome_kind not in set(expected.accepted_outcome_kinds):
            return "revenue_outcome_kind_not_accepted"

        if expected.require_reference and not revenue_reference:
            return "missing_revenue_reference"

        if expected.require_positive_revenue and revenue_amount <= 0.0:
            return "non_positive_revenue"

        if revenue_amount < float(expected.min_revenue_amount):
            return "revenue_below_minimum"

        return None


__all__ = [
    "CANON_REVENUE_VERIFICATION",
    "RevenueVerification",
    "RevenueVerificationExpectation",
    "RevenueVerificationResult",
]
