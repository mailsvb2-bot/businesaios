from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from execution.error_family_classifier import ErrorFamilyClassifier
from application.learning.failure_pattern_detector import FailureEvent
from execution.retry_adaptation_policy import RetryAdaptationPolicy
from application.learning.retry_learning_engine import RetryLearningEngine
from application.learning.retry_learning_store import RetryLearningSnapshot, RetryLearningStore


CANON_SELF_HEALING_RETRY = True
_MAX_RECENT_RETRY_EVENTS = 64
_ALLOWED_RETRY_KINDS = frozenset({"success", "recoverable", "operator_required", "non_recoverable"})


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}




def _normalize_retry_kind(value: object) -> str:
    token = str(value or "").strip().lower()
    if not token:
        return "non_recoverable"
    if token in _ALLOWED_RETRY_KINDS:
        return token
    return "non_recoverable"

def _safe_events(value: object) -> tuple[Mapping[str, Any] | FailureEvent, ...]:
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, dict)):
        result: list[Mapping[str, Any] | FailureEvent] = []
        for item in value:
            if isinstance(item, FailureEvent) or isinstance(item, Mapping):
                result.append(item)
        if len(result) <= _MAX_RECENT_RETRY_EVENTS:
            return tuple(result)
        return tuple(result[-_MAX_RECENT_RETRY_EVENTS:])
    return ()


@dataclass(frozen=True)
class SelfHealingRetryDecision:
    should_retry: bool
    retry_kind: str
    backoff_seconds: int
    recovery_mode: str
    fallback_action_type: str | None
    reason: str
    error_family: str = 'unknown'
    cooldown_seconds: int = 0
    should_open_operator_handoff: bool = False
    should_quarantine_capability: bool = False
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "should_retry": bool(self.should_retry),
            "retry_kind": str(self.retry_kind),
            "backoff_seconds": int(self.backoff_seconds),
            "recovery_mode": str(self.recovery_mode),
            "fallback_action_type": self.fallback_action_type,
            "reason": str(self.reason),
            "error_family": str(self.error_family),
            "cooldown_seconds": int(self.cooldown_seconds),
            "should_open_operator_handoff": bool(self.should_open_operator_handoff),
            "should_quarantine_capability": bool(self.should_quarantine_capability),
            "confidence": float(self.confidence),
            "evidence_only": True,
            "must_not_issue_decision": True,
        }


class SelfHealingRetryEngine:
    def __init__(
        self,
        *,
        learning_store: RetryLearningStore | None = None,
        policy: RetryAdaptationPolicy | None = None,
        error_family_classifier: ErrorFamilyClassifier | None = None,
        retry_learning_engine: RetryLearningEngine | None = None,
    ) -> None:
        self._learning_store = learning_store
        self._policy = policy or RetryAdaptationPolicy()
        self._classifier = error_family_classifier or ErrorFamilyClassifier()
        self._retry_learning_engine = retry_learning_engine or RetryLearningEngine(
            learning_store=learning_store,
            error_family_classifier=self._classifier,
        )

    def _learning_snapshot(self, *, feedback: Mapping[str, Any], action_type: str, error_family: str) -> RetryLearningSnapshot | None:
        if self._learning_store is None:
            return None
        tenant_id = str(feedback.get('tenant_id') or 'default').strip()
        return self._learning_store.load(tenant_id=tenant_id, action_type=action_type, error_family=error_family)

    def _persist_learning(
        self,
        *,
        feedback: Mapping[str, Any],
        action_type: str,
        error_family: str,
        result_error: str | None,
        decision: SelfHealingRetryDecision,
        attempt_index: int,
    ) -> None:
        if self._retry_learning_engine is not None:
            self._retry_learning_engine.record_outcome(
                tenant_id=str(feedback.get('tenant_id') or 'default').strip(),
                action_type=action_type,
                retry_kind=decision.retry_kind,
                result_error=result_error,
                backoff_seconds=decision.backoff_seconds,
                attempt_index=attempt_index,
            )
            return
        if self._learning_store is None:
            return
        tenant_id = str(feedback.get('tenant_id') or 'default').strip()
        current = self._learning_store.load(tenant_id=tenant_id, action_type=action_type, error_family=error_family)
        updated = RetryLearningSnapshot(
            tenant_id=tenant_id,
            action_type=action_type,
            error_family=error_family,
            attempts=current.attempts + 1,
            successes_after_retry=current.successes_after_retry + int(decision.retry_kind == 'success' and int(attempt_index) > 0),
            last_backoff_seconds=decision.backoff_seconds,
        )
        self._learning_store.save(updated)

    def evaluate(self, *, action_type: str, retry_kind: str, result_error: str | None, feedback: Mapping[str, Any] | None, attempt_index: int) -> SelfHealingRetryDecision:
        body = _safe_dict(feedback)
        normalized_retry_kind = _normalize_retry_kind(retry_kind)
        error_family = self._classifier.classify(result_error)
        recent_events = _safe_events(body.get('recent_retry_events') or body.get('retry_failure_events'))
        if normalized_retry_kind not in {'success', 'recoverable', 'operator_required'}:
            learning_snapshot = self._learning_snapshot(feedback=body, action_type=action_type, error_family=error_family)
            adapted = self._policy.evaluate(action_type=action_type, retry_kind=normalized_retry_kind, result_error=result_error, attempt_index=attempt_index, learning_snapshot=learning_snapshot)
            decision = SelfHealingRetryDecision(
                should_retry=adapted.should_retry,
                retry_kind=normalized_retry_kind,
                backoff_seconds=adapted.backoff_seconds,
                recovery_mode=adapted.recovery_mode,
                fallback_action_type=adapted.fallback_action_type,
                reason=adapted.reason,
                error_family=error_family,
            )
            self._persist_learning(feedback=body, action_type=action_type, error_family=error_family, result_error=result_error, decision=decision, attempt_index=attempt_index)
            return decision
        if self._retry_learning_engine is not None:
            recommendation = self._retry_learning_engine.recommend(
                tenant_id=str(body.get('tenant_id') or 'default').strip(),
                business_id=str(body.get('business_id') or '').strip(),
                action_type=action_type,
                retry_kind=normalized_retry_kind,
                result_error=result_error,
                attempt_index=attempt_index,
                feedback=body,
                recent_events=recent_events,
                recovery_mode=str(body.get('recovery_mode') or '').strip(),
            )
            decision = SelfHealingRetryDecision(
                should_retry=recommendation.should_retry,
                retry_kind=normalized_retry_kind,
                backoff_seconds=recommendation.recommended_backoff_seconds,
                recovery_mode=recommendation.recommended_recovery_mode,
                fallback_action_type=recommendation.fallback_action_type,
                reason=recommendation.reason,
                error_family=error_family,
                cooldown_seconds=recommendation.cooldown_seconds,
                should_open_operator_handoff=recommendation.should_open_operator_handoff,
                should_quarantine_capability=recommendation.should_quarantine_capability,
                confidence=recommendation.confidence,
            )
            self._persist_learning(feedback=body, action_type=action_type, error_family=error_family, result_error=result_error, decision=decision, attempt_index=attempt_index)
            return decision
        if normalized_retry_kind == "success":
            decision = SelfHealingRetryDecision(False, "success", 0, "none", None, "execution_ok", error_family=error_family)
            self._persist_learning(feedback=body, action_type=action_type, error_family=error_family, result_error=result_error, decision=decision, attempt_index=attempt_index)
            return decision
        if normalized_retry_kind == "operator_required" or body.get("approval_required") or body.get("blocked_by_policy"):
            decision = SelfHealingRetryDecision(False, "operator_required", 0, "operator_handoff", None, "operator_or_policy_gate", error_family=error_family, should_open_operator_handoff=True)
            self._persist_learning(feedback=body, action_type=action_type, error_family=error_family, result_error=result_error, decision=decision, attempt_index=attempt_index)
            return decision
        learning_snapshot = self._learning_snapshot(feedback=body, action_type=action_type, error_family=error_family)
        adapted = self._policy.evaluate(action_type=action_type, retry_kind=normalized_retry_kind, result_error=result_error, attempt_index=attempt_index, learning_snapshot=learning_snapshot)
        decision = SelfHealingRetryDecision(
            should_retry=adapted.should_retry,
            retry_kind=normalized_retry_kind,
            backoff_seconds=adapted.backoff_seconds,
            recovery_mode=adapted.recovery_mode,
            fallback_action_type=adapted.fallback_action_type,
            reason=adapted.reason,
            error_family=error_family,
        )
        self._persist_learning(feedback=body, action_type=action_type, error_family=error_family, result_error=result_error, decision=decision, attempt_index=attempt_index)
        return decision


__all__ = ["CANON_SELF_HEALING_RETRY", "SelfHealingRetryDecision", "SelfHealingRetryEngine"]
