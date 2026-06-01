from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from application.effects.effect_outcome_vocabulary import normalize_outcome_status, outcome_is_verified
from application.effects.effect_verification_bridge import normalize_feedback_contract, normalize_router_evidence
from application.evidence.effect_evidence import EffectEvidenceBuilder
from execution.outcome_verifier import OutcomeExpectation, expectation_from_action
from execution.verification.verification_engine import (
    VerificationEngine,
    connector_snapshot_evidence,
    execution_receipt_evidence,
)
from execution.verification.verification_engine import (
    router_evidence as verification_router_evidence,
)

CANON_EVIDENCE_VERIFIER = True


def _text(value: object) -> str:
    return str(value or "").strip()


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _safe_list(value: object) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = _text(value)
    return [text] if text else []


def _coerce_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    text = _text(value).casefold()
    if text in {"true", "1", "yes", "ok", "success", "verified"}:
        return True
    if text in {"false", "0", "no", "failed", "error", "unverified"}:
        return False
    return None


@dataclass(frozen=True, slots=True)
class EvidenceVerificationContext:
    action: dict[str, Any]
    execution_receipt: dict[str, Any] = field(default_factory=dict)
    feedback_snapshot: dict[str, Any] = field(default_factory=dict)
    router_result: dict[str, Any] = field(default_factory=dict)
    expectation: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": dict(self.action),
            "execution_receipt": dict(self.execution_receipt),
            "feedback_snapshot": dict(self.feedback_snapshot),
            "router_result": dict(self.router_result),
            "expectation": dict(self.expectation),
        }


@dataclass(frozen=True, slots=True)
class EvidenceVerificationResult:
    verified: bool
    evidence_bundle: dict[str, Any]
    verification: dict[str, Any]
    context: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "verified": self.verified,
            "evidence_bundle": dict(self.evidence_bundle),
            "verification": dict(self.verification),
            "context": dict(self.context),
        }


class EvidenceVerifier:
    def __init__(self, *, verification_engine: VerificationEngine | None = None) -> None:
        self._verification_engine = verification_engine or VerificationEngine()

    def verify(
        self,
        *,
        action: Mapping[str, Any],
        execution_receipt: Mapping[str, Any] | None = None,
        feedback: Mapping[str, Any] | None = None,
        router_evidence: Mapping[str, Any] | None = None,
        expectation: OutcomeExpectation | None = None,
    ) -> EvidenceVerificationResult:
        action_payload = _safe_dict(action)
        action_type = _text(action_payload.get("action_type"))
        action_id = _text(action_payload.get("action_id"))
        receipt_payload = _safe_dict(execution_receipt)
        feedback_payload = normalize_feedback_contract(feedback)
        router_payload = normalize_router_evidence(router_evidence)

        builder = EffectEvidenceBuilder(action_type=action_type, action_id=action_id)
        evidence_items = []

        if receipt_payload:
            builder.add_execution_receipt(payload=receipt_payload)
            evidence_items.append(
                execution_receipt_evidence(
                    action_id=action_id,
                    action_type=action_type,
                    ok=bool(receipt_payload.get("ok", receipt_payload.get("executed", False))),
                    status=_text(receipt_payload.get("status")) or ("observed" if receipt_payload.get("ok", receipt_payload.get("executed", False)) else "failed"),
                    source=_text(receipt_payload.get("source") or "executor"),
                    confidence=1.0 if receipt_payload.get("ok", receipt_payload.get("executed", False)) else 0.0,
                    payload=receipt_payload,
                )
            )

        evidence_block = _safe_dict(feedback_payload.get("evidence"))
        router_from_feedback = _safe_dict(evidence_block.get("router_result"))
        if router_from_feedback:
            builder.add_feedback_evidence(feedback=feedback_payload)
            rf_verified = _coerce_bool(router_from_feedback.get("verified"))
            evidence_items.append(
                verification_router_evidence(
                    action_id=action_id,
                    action_type=action_type,
                    verified=bool(rf_verified),
                    status=_text(router_from_feedback.get("status") or feedback_payload.get("verification_status") or "pending"),
                    source=_text(router_from_feedback.get("source") or "effect_router"),
                    external_refs=_safe_list(router_from_feedback.get("external_refs") or feedback_payload.get("external_refs")),
                    confidence=float(router_from_feedback.get("confidence") or feedback_payload.get("verification_confidence") or 0.0),
                    payload=router_from_feedback,
                )
            )

        if router_payload:
            builder.add_router_evidence(payload=router_payload)
            r_verified = _coerce_bool(router_payload.get("verified"))
            evidence_items.append(
                verification_router_evidence(
                    action_id=action_id,
                    action_type=action_type,
                    verified=bool(r_verified),
                    status=_text(router_payload.get("status") or "pending"),
                    source=_text(router_payload.get("source") or "effect_router"),
                    external_refs=_safe_list(router_payload.get("external_refs")),
                    confidence=float(router_payload.get("confidence") or 0.0),
                    payload=router_payload,
                )
            )

        connector_rows = evidence_block.get("connector_snapshots") or feedback_payload.get("connector_snapshots") or ()
        if isinstance(connector_rows, Mapping):
            connector_rows = [connector_rows]
        for row in connector_rows:
            connector_payload = _safe_dict(row)
            if not connector_payload:
                continue
            builder.add_connector_snapshot(source=_text(connector_payload.get("source") or "connector"), payload=connector_payload)
            c_verified = _coerce_bool(connector_payload.get("verified"))
            if c_verified is None:
                c_verified = normalize_outcome_status(connector_payload.get("status"), default="unknown") == "verified"
            evidence_items.append(
                connector_snapshot_evidence(
                    action_id=action_id,
                    action_type=action_type,
                    verified=bool(c_verified),
                    source=_text(connector_payload.get("source") or "connector"),
                    status=_text(connector_payload.get("status") or ("verified" if c_verified else "failed")),
                    external_refs=_safe_list(connector_payload.get("external_refs") or connector_payload.get("external_ref")),
                    confidence=float(connector_payload.get("confidence") or 0.0),
                    payload=connector_payload,
                )
            )

        generic_evidence = evidence_block if evidence_block and not router_from_feedback else {}
        if generic_evidence:
            generic_refs = _safe_list(generic_evidence.get("external_refs") or feedback_payload.get("external_refs"))
            if generic_refs or _text(generic_evidence.get("status")):
                generic_verified = _coerce_bool(feedback_payload.get("verified"))
                if generic_verified is None:
                    generic_verified = normalize_outcome_status(generic_evidence.get("status"), default="unknown") == "verified"
                builder.add_connector_snapshot(source=_text(generic_evidence.get("source") or "feedback_connector"), payload={**generic_evidence, "external_refs": generic_refs})
                evidence_items.append(
                    connector_snapshot_evidence(
                        action_id=action_id,
                        action_type=action_type,
                        verified=bool(generic_verified),
                        source=_text(generic_evidence.get("source") or "feedback_connector"),
                        status=_text(generic_evidence.get("status") or ("verified" if generic_verified else "failed")),
                        external_refs=generic_refs,
                        confidence=float(generic_evidence.get("confidence") or feedback_payload.get("verification_confidence") or 0.0),
                        payload={**generic_evidence, "external_refs": generic_refs},
                    )
                )

        evidence_bundle = builder.build()
        expected = expectation or expectation_from_action(
            action_type,
            external_confirmation_mode=_text(action_payload.get("external_confirmation_mode") or "required"),
        )
        engine_result = self._verification_engine.verify(action=action_payload, evidence=evidence_items).to_dict()
        decision = _safe_dict(engine_result.get("decision"))
        source_of_truth = _text(decision.get("source_of_truth") or "observable_evidence")
        if source_of_truth == "effect_router":
            source_of_truth = "router"
        verification_status = normalize_outcome_status(
            decision.get("status") or decision.get("code"),
            verified=decision.get("verified"),
            retryable=decision.get("retryable"),
            default="unknown",
        )
        verified = outcome_is_verified(
            verification_status,
            verified=decision.get("verified"),
            retryable=decision.get("retryable"),
        )
        confidence = float(decision.get("confidence") or evidence_bundle.max_confidence() or 0.0)
        external_refs = list(decision.get("observed_external_refs") or evidence_bundle.external_refs())
        outcome_status = verification_status
        if (not verified) and expected.external_confirmation_mode == "required" and not external_refs and verification_status in {"missing_evidence", "pending", "retryable", "unknown", "unverified"}:
            outcome_status = "missing_external_confirmation"
        outcome_payload = {
            "action_type": action_type,
            "action_id": action_id,
            "verified": verified,
            "verification_status": outcome_status,
            "reason": _text(decision.get("reason") or decision.get("code")),
            "matched_records": len(decision.get("matched_evidence_ids") or []),
            "external_matched_records": max(1 if external_refs and verified else 0, len([i for i in evidence_items if getattr(i, "is_authoritative", lambda: False)() and getattr(i, "is_positive", lambda: False)()])),
            "total_records": len(evidence_bundle.records),
            "evidence": evidence_bundle.to_dict(),
            "expectation": expected.to_dict(),
        }
        if router_payload:
            explicit_verified = _coerce_bool(router_payload.get("verified"))
            if explicit_verified is not None:
                verification_status = normalize_outcome_status(
                    router_payload.get("status") or router_payload.get("code") or verification_status,
                    verified=explicit_verified,
                    retryable=router_payload.get("retryable"),
                    default=verification_status,
                )
                verified = outcome_is_verified(
                    verification_status,
                    verified=explicit_verified,
                    retryable=router_payload.get("retryable"),
                )
                source_of_truth = "router"
                confidence = float(router_payload.get("confidence") or confidence or 0.0)
                external_refs = _safe_list(router_payload.get("external_refs")) or external_refs
                outcome_payload["verified"] = verified
                outcome_payload["verification_status"] = verification_status if verified else outcome_payload["verification_status"]
        verification_payload = {
            "verified": verified,
            "status": verification_status,
            "code": _text(router_payload.get("code") if router_payload else "") or _text(decision.get("code") or verification_status),
            "message": _text(router_payload.get("message") if router_payload else "") or _text(decision.get("reason") or ""),
            "confidence": confidence,
            "external_refs": external_refs,
            "source_of_truth": source_of_truth,
            "retryable": bool((router_payload or {}).get("retryable", decision.get("retryable", False))),
            "timed_out": bool(decision.get("timed_out", False)),
            "delayed": bool(decision.get("delayed", False)),
            "decision_fingerprint": _text(decision.get("decision_fingerprint")),
            "matched_evidence_ids": list(decision.get("matched_evidence_ids") or []),
            "conflicting_evidence_ids": list(decision.get("conflicting_evidence_ids") or []),
            "pending_evidence_ids": list(decision.get("pending_evidence_ids") or []),
            "engine": engine_result,
            "outcome": outcome_payload,
        }
        context = EvidenceVerificationContext(
            action=action_payload,
            execution_receipt=receipt_payload,
            feedback_snapshot=feedback_payload,
            router_result=router_payload,
            expectation=expected.to_dict(),
        )
        return EvidenceVerificationResult(
            verified=verified,
            evidence_bundle=evidence_bundle.to_dict(),
            verification=verification_payload,
            context=context.to_dict(),
        )


__all__ = [
    "CANON_EVIDENCE_VERIFIER",
    "EvidenceVerificationContext",
    "EvidenceVerificationResult",
    "EvidenceVerifier",
]
