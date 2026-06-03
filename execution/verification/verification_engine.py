from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from collections.abc import Iterable, Mapping
from execution.verification.delayed_verification_retry import DelayedVerificationRetry
from execution.verification.evidence_correlation import EvidenceCorrelation, EvidenceCorrelationResult
from execution.verification.evidence_persistence import VerificationEvidencePersistence
from execution.verification.evidence_types import (
    EVIDENCE_KIND_CONNECTOR_SNAPSHOT,
    EVIDENCE_KIND_EXECUTION_RECEIPT,
    EVIDENCE_KIND_ROUTER_RESULT,
    EvidenceItem,
)
from execution.verification.idempotent_verifier import IdempotentVerifier
from execution.verification.source_of_truth_policy import SourceOfTruthPolicy, SourceOfTruthResolution
from execution.verification.verification_contract import (
    VerificationDecision,
    VerificationPolicy,
    VerificationRequest,
    evidence_item_from_mapping,
    verification_policy_from_action,
)
from execution.verification.verification_timeout_policy import VerificationTimeoutPolicy, VerificationTimeoutState
CANON_VERIFICATION_ENGINE = True
def _text(value: object) -> str:
    return str(value or "").strip()
def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}
def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)
def _unique_refs(evidence: Iterable[EvidenceItem]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in evidence:
        for ref in item.external_refs:
            if ref not in seen:
                seen.add(ref)
                ordered.append(ref)
    return tuple(ordered)
@dataclass(frozen=True, slots=True)
class VerificationEngineResult:
    request: dict[str, Any]
    policy: dict[str, Any]
    decision: dict[str, Any]
    evidence: tuple[dict[str, Any], ...]
    correlation: dict[str, Any]
    source_of_truth: dict[str, Any]
    timeout_state: dict[str, Any]
    retry_plan: dict[str, Any]
    persistence: dict[str, Any]
    def to_dict(self) -> dict[str, Any]:
        return {
            "request": dict(self.request),
            "policy": dict(self.policy),
            "decision": dict(self.decision),
            "evidence": [dict(item) for item in self.evidence],
            "correlation": dict(self.correlation),
            "source_of_truth": dict(self.source_of_truth),
            "timeout_state": dict(self.timeout_state),
            "retry_plan": dict(self.retry_plan),
            "persistence": dict(self.persistence),
        }
class VerificationEngine:
    def __init__(
        self,
        *,
        source_of_truth_policy: SourceOfTruthPolicy | None = None,
        correlation: EvidenceCorrelation | None = None,
        timeout_policy: VerificationTimeoutPolicy | None = None,
        retry: DelayedVerificationRetry | None = None,
        persistence: VerificationEvidencePersistence | None = None,
        idempotent_verifier: IdempotentVerifier | None = None,
    ) -> None:
        self._source_of_truth_policy = source_of_truth_policy or SourceOfTruthPolicy()
        self._correlation = correlation or EvidenceCorrelation()
        self._timeout_policy = timeout_policy or VerificationTimeoutPolicy()
        self._retry = retry or DelayedVerificationRetry()
        self._persistence = persistence or VerificationEvidencePersistence()
        self._idempotent_verifier = idempotent_verifier or IdempotentVerifier()
    def verify(
        self,
        *,
        action: Mapping[str, Any],
        evidence: Iterable[EvidenceItem | Mapping[str, Any]] | None = None,
        now: datetime | None = None,
        attempt_index: int = 0,
    ) -> VerificationEngineResult:
        policy = verification_policy_from_action(action)
        request = VerificationRequest.from_payload(action=action)
        raw_evidence = self._normalize_evidence(action=action, evidence=evidence)
        correlation = self._correlation.correlate(raw_evidence)
        evidence_items = self._select_unique_evidence(correlation)
        request = VerificationRequest.from_payload(action=action, evidence=evidence_items)
        timeout_state = self._timeout_policy.evaluate(request=request, policy=policy, now=now)
        source_resolution = self._source_of_truth_policy.resolve(evidence_items)
        fingerprint, cached = self._idempotent_verifier.get_cached(request=request, evidence=evidence_items)
        if cached is not None:
            cached_decision = VerificationDecision(
                action_id=cached.action_id,
                action_type=cached.action_type,
                verified=cached.verified,
                status=cached.status,
                code=cached.code,
                reason=cached.reason,
                source_of_truth=cached.source_of_truth,
                confidence=cached.confidence,
                observed_external_refs=cached.observed_external_refs,
                matched_evidence_ids=cached.matched_evidence_ids,
                conflicting_evidence_ids=cached.conflicting_evidence_ids,
                pending_evidence_ids=cached.pending_evidence_ids,
                retryable=cached.retryable,
                delayed=cached.delayed,
                timed_out=cached.timed_out,
                decision_fingerprint=fingerprint,
                decided_at=cached.decided_at,
                policy_snapshot=cached.policy_snapshot,
                summary=cached.summary,
            )
            retry_plan = self._retry.plan(
                request=request,
                policy=policy,
                decision=cached_decision,
                timeout_state=timeout_state,
                attempt_index=attempt_index,
                now=now,
            )
            persistence = self._persistence.build_artifacts(
                request=request,
                decision=cached_decision,
                evidence=evidence_items,
                retry_plan=retry_plan.to_dict(),
            )
            return VerificationEngineResult(
                request=request.to_dict(),
                policy=policy.to_dict(),
                decision=cached_decision.to_dict(),
                evidence=tuple(item.to_dict() for item in evidence_items),
                correlation=correlation.to_dict(),
                source_of_truth=source_resolution.to_dict(),
                timeout_state=timeout_state.to_dict(),
                retry_plan=retry_plan.to_dict(),
                persistence=persistence.to_dict(),
            )
        decision = self._decide(
            request=request,
            policy=policy,
            evidence=evidence_items,
            correlation=correlation,
            source_of_truth=source_resolution,
            timeout_state=timeout_state,
            decision_fingerprint=fingerprint,
        )
        self._idempotent_verifier.remember(request=request, evidence=evidence_items, decision=decision)
        retry_plan = self._retry.plan(
            request=request,
            policy=policy,
            decision=decision,
            timeout_state=timeout_state,
            attempt_index=attempt_index,
            now=now,
        )
        persistence = self._persistence.build_artifacts(
            request=request,
            decision=decision,
            evidence=evidence_items,
            retry_plan=retry_plan.to_dict(),
        )
        return VerificationEngineResult(
            request=request.to_dict(),
            policy=policy.to_dict(),
            decision=decision.to_dict(),
            evidence=tuple(item.to_dict() for item in evidence_items),
            correlation=correlation.to_dict(),
            source_of_truth=source_resolution.to_dict(),
            timeout_state=timeout_state.to_dict(),
            retry_plan=retry_plan.to_dict(),
            persistence=persistence.to_dict(),
        )
    def _normalize_evidence(self, *, action: Mapping[str, Any], evidence: Iterable[EvidenceItem | Mapping[str, Any]] | None) -> tuple[EvidenceItem, ...]:
        action_payload = _safe_dict(action)
        action_id = _text(action_payload.get("action_id"))
        action_type = _text(action_payload.get("action_type"))
        rows: list[EvidenceItem] = []
        for item in evidence or ():
            if isinstance(item, EvidenceItem):
                rows.append(item)
                continue
            payload = _safe_dict(item)
            if not payload:
                continue
            payload.setdefault("action_id", action_id)
            payload.setdefault("action_type", action_type)
            rows.append(evidence_item_from_mapping(payload))
        return tuple(rows)
    def _select_unique_evidence(self, correlation: EvidenceCorrelationResult) -> tuple[EvidenceItem, ...]:
        selected: list[EvidenceItem] = []
        seen: set[str] = set()
        for group in correlation.groups:
            for item in group.evidence:
                if item.evidence_id in seen:
                    continue
                seen.add(item.evidence_id)
                selected.append(item)
        return tuple(selected)
    def _decide(
        self,
        *,
        request: VerificationRequest,
        policy: VerificationPolicy,
        evidence: tuple[EvidenceItem, ...],
        correlation: EvidenceCorrelationResult,
        source_of_truth: SourceOfTruthResolution,
        timeout_state: VerificationTimeoutState,
        decision_fingerprint: str,
    ) -> VerificationDecision:
        positive = tuple(item for item in evidence if item.is_positive() and float(item.confidence) >= float(policy.positive_confidence_threshold))
        authoritative_positive = tuple(item for item in positive if item.is_authoritative())
        negative = tuple(item for item in evidence if item.is_negative())
        pending = tuple(item for item in evidence if item.is_pending())
        conflicts = tuple(item for item in correlation.conflicting_evidence)
        matched = tuple(item for item in correlation.matched_evidence)
        observed_refs = _unique_refs(evidence)
        summary = {
            "positive_count": len(positive),
            "negative_count": len(negative),
            "authoritative_positive_count": len(authoritative_positive),
            "pending_count": len(pending),
            "conflict_count": len(conflicts),
            "duplicate_evidence_count": len(correlation.duplicate_evidence_ids),
            "orphan_evidence_count": len(correlation.orphan_evidence),
            "leader_evidence_id": source_of_truth.leader_evidence_id,
        }
        if conflicts and policy.conflict_is_terminal:
            return VerificationDecision(
                action_id=request.action_id,
                action_type=request.action_type,
                verified=False,
                status="conflicting",
                code="conflicting_evidence",
                reason="correlated_evidence_disagrees",
                source_of_truth=source_of_truth.source_of_truth,
                confidence=0.0,
                observed_external_refs=observed_refs,
                matched_evidence_ids=tuple(item.evidence_id for item in matched),
                conflicting_evidence_ids=tuple(item.evidence_id for item in conflicts),
                pending_evidence_ids=tuple(item.evidence_id for item in pending),
                retryable=False,
                delayed=False,
                timed_out=False,
                decision_fingerprint=decision_fingerprint,
                policy_snapshot=policy.to_dict(),
                summary=summary,
            )
        if timeout_state.expired:
            return VerificationDecision(
                action_id=request.action_id,
                action_type=request.action_type,
                verified=False,
                status="timed_out",
                code="verification_timeout",
                reason="verification_deadline_expired",
                source_of_truth=source_of_truth.source_of_truth,
                confidence=max((_safe_float(item.confidence) for item in positive), default=0.0),
                observed_external_refs=observed_refs,
                matched_evidence_ids=tuple(item.evidence_id for item in matched),
                conflicting_evidence_ids=(),
                pending_evidence_ids=tuple(item.evidence_id for item in pending),
                retryable=False,
                delayed=False,
                timed_out=True,
                decision_fingerprint=decision_fingerprint,
                policy_snapshot=policy.to_dict(),
                summary=summary,
            )
        enough_evidence = len(positive) >= max(0, int(policy.min_evidence_count))
        external_satisfied = (not policy.require_external_evidence) or bool(authoritative_positive)
        authoritative_satisfied = (not policy.require_authoritative_source) or bool(source_of_truth.authoritative_positive_evidence)
        if enough_evidence and external_satisfied and authoritative_satisfied:
            confidence = max((_safe_float(item.confidence, default=0.0) for item in positive), default=0.0)
            return VerificationDecision(
                action_id=request.action_id,
                action_type=request.action_type,
                verified=True,
                status="verified",
                code="verified",
                reason="external_verification_satisfied",
                source_of_truth=source_of_truth.source_of_truth,
                confidence=confidence,
                observed_external_refs=observed_refs,
                matched_evidence_ids=tuple(item.evidence_id for item in matched),
                conflicting_evidence_ids=(),
                pending_evidence_ids=tuple(item.evidence_id for item in pending),
                retryable=False,
                delayed=False,
                timed_out=False,
                decision_fingerprint=decision_fingerprint,
                policy_snapshot=policy.to_dict(),
                summary=summary,
            )
        if pending and policy.allow_delayed_verification:
            confidence = max((_safe_float(item.confidence, default=0.0) for item in positive), default=0.0)
            return VerificationDecision(
                action_id=request.action_id,
                action_type=request.action_type,
                verified=False,
                status="pending",
                code="verification_pending",
                reason="waiting_for_external_evidence",
                source_of_truth=source_of_truth.source_of_truth,
                confidence=confidence,
                observed_external_refs=observed_refs,
                matched_evidence_ids=tuple(item.evidence_id for item in matched),
                conflicting_evidence_ids=(),
                pending_evidence_ids=tuple(item.evidence_id for item in pending),
                retryable=True,
                delayed=True,
                timed_out=False,
                decision_fingerprint=decision_fingerprint,
                policy_snapshot=policy.to_dict(),
                summary=summary,
            )
        return VerificationDecision(
            action_id=request.action_id,
            action_type=request.action_type,
            verified=False,
            status="missing_evidence",
            code="missing_external_evidence",
            reason="required_external_evidence_not_observed",
            source_of_truth=source_of_truth.source_of_truth,
            confidence=max((_safe_float(item.confidence, default=0.0) for item in positive), default=0.0),
            observed_external_refs=observed_refs,
            matched_evidence_ids=tuple(item.evidence_id for item in matched),
            conflicting_evidence_ids=(),
            pending_evidence_ids=tuple(item.evidence_id for item in pending),
            retryable=policy.allow_delayed_verification,
            delayed=False,
            timed_out=False,
            decision_fingerprint=decision_fingerprint,
            policy_snapshot=policy.to_dict(),
            summary=summary,
        )
def execution_receipt_evidence(*, action_id: str, action_type: str, ok: bool, status: str = "", source: str = "executor", confidence: float = 1.0, payload: Mapping[str, Any] | None = None) -> EvidenceItem:
    return EvidenceItem(
        evidence_id="",
        action_id=action_id,
        action_type=action_type,
        source=source,
        kind=EVIDENCE_KIND_EXECUTION_RECEIPT,
        status=status or ("observed" if ok else "failed"),
        confidence=confidence if ok else 0.0,
        payload=dict(payload or {}),
    )
def router_evidence(*, action_id: str, action_type: str, verified: bool, status: str = "", source: str = "effect_router", external_refs: tuple[str, ...] | list[str] = (), confidence: float = 1.0, payload: Mapping[str, Any] | None = None) -> EvidenceItem:
    effective_status = status or ("verified" if verified else "failed")
    if effective_status == "pending":
        effective_confidence = min(float(confidence), 0.49)
    else:
        effective_confidence = confidence if verified else 0.0
    return EvidenceItem(
        evidence_id="",
        action_id=action_id,
        action_type=action_type,
        source=source,
        kind=EVIDENCE_KIND_ROUTER_RESULT,
        status=effective_status,
        external_refs=tuple(external_refs),
        confidence=effective_confidence,
        payload=dict(payload or {}),
    )
def connector_snapshot_evidence(*, action_id: str, action_type: str, verified: bool, source: str, external_refs: tuple[str, ...] | list[str] = (), status: str = "", confidence: float = 1.0, payload: Mapping[str, Any] | None = None) -> EvidenceItem:
    return EvidenceItem(
        evidence_id="",
        action_id=action_id,
        action_type=action_type,
        source=source,
        kind=EVIDENCE_KIND_CONNECTOR_SNAPSHOT,
        status=status or ("verified" if verified else "failed"),
        external_refs=tuple(external_refs),
        confidence=confidence if verified else 0.0,
        payload=dict(payload or {}),
    )
__all__ = [
    "CANON_VERIFICATION_ENGINE",
    "VerificationEngineResult",
    "VerificationEngine",
    "execution_receipt_evidence",
    "router_evidence",
    "connector_snapshot_evidence",
]
