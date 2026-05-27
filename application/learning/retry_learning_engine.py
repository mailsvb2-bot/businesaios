from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from application.learning.failure_pattern_detector import (
    FailureEvent,
    FailurePattern,
    FailurePatternDetector,
    FailurePatternReport,
)
from application.learning.retry_learning_store import RetryLearningSnapshot, RetryLearningStore
from execution.error_family_classifier import ErrorFamilyClassifier

CANON_RETRY_LEARNING_ENGINE = True
RETRY_LEARNING_SCHEMA_VERSION = 1

_DEFAULT_MAX_ATTEMPTS = 3
_MAX_RATE_LIMIT_BACKOFF_SECONDS = 900
_MAX_TRANSPORT_BACKOFF_SECONDS = 300
_MAX_GENERIC_BACKOFF_SECONDS = 180


def _text(value: object) -> str:
    return str(value or "").strip()


def _text_lower(value: object) -> str:
    return _text(value).lower()


def _safe_int(value: object, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _safe_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return _text_lower(value) in {"1", "true", "yes", "y", "on"}


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _clamp_unit(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return float(value)


def _severity_bonus(severity: str) -> int:
    return {
        "low": 0,
        "medium": 1,
        "high": 2,
        "critical": 3,
    }.get(_text_lower(severity), 0)


@dataclass(frozen=True)
class RetryLearningContext:
    tenant_id: str = ""
    business_id: str = ""
    action_type: str = ""
    error_family: str = "unknown"
    retry_kind: str = ""
    attempt_index: int = 0
    result_error: str = ""
    capability: str = ""
    service_name: str = ""
    recovery_mode: str = ""
    blocked_by_policy: bool = False
    approval_required: bool = False
    operator_required: bool = False
    learned_attempts: int = 0
    learned_success_after_retry_rate: float = 0.0
    learned_last_backoff_seconds: int = 0
    recurring_pattern_count: int = 0
    dominant_pattern_severity: str = "low"
    dominant_pattern_failures: int = 0
    dominant_pattern_should_cooldown: bool = False
    dominant_pattern_should_quarantine_capability: bool = False
    evidence_only: bool = True
    must_not_issue_decision: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": str(self.tenant_id),
            "business_id": str(self.business_id),
            "action_type": str(self.action_type),
            "error_family": str(self.error_family),
            "retry_kind": str(self.retry_kind),
            "attempt_index": int(self.attempt_index),
            "result_error": str(self.result_error),
            "capability": str(self.capability),
            "service_name": str(self.service_name),
            "recovery_mode": str(self.recovery_mode),
            "blocked_by_policy": bool(self.blocked_by_policy),
            "approval_required": bool(self.approval_required),
            "operator_required": bool(self.operator_required),
            "learned_attempts": int(self.learned_attempts),
            "learned_success_after_retry_rate": float(self.learned_success_after_retry_rate),
            "learned_last_backoff_seconds": int(self.learned_last_backoff_seconds),
            "recurring_pattern_count": int(self.recurring_pattern_count),
            "dominant_pattern_severity": str(self.dominant_pattern_severity),
            "dominant_pattern_failures": int(self.dominant_pattern_failures),
            "dominant_pattern_should_cooldown": bool(self.dominant_pattern_should_cooldown),
            "dominant_pattern_should_quarantine_capability": bool(self.dominant_pattern_should_quarantine_capability),
            "evidence_only": True,
            "must_not_issue_decision": True,
        }


@dataclass(frozen=True)
class RetryLearningRecommendation:
    schema_version: int = RETRY_LEARNING_SCHEMA_VERSION
    tenant_id: str = ""
    business_id: str = ""
    action_type: str = ""
    error_family: str = "unknown"
    should_retry: bool = False
    recommended_recovery_mode: str = "stop"
    recommended_backoff_seconds: int = 0
    recommended_max_attempts: int = 1
    cooldown_seconds: int = 0
    fallback_action_type: str | None = None
    should_open_operator_handoff: bool = False
    should_quarantine_capability: bool = False
    confidence: float = 0.0
    reason: str = ""
    context: RetryLearningContext = field(default_factory=RetryLearningContext)
    evidence_only: bool = True
    must_not_issue_decision: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "tenant_id": str(self.tenant_id),
            "business_id": str(self.business_id),
            "action_type": str(self.action_type),
            "error_family": str(self.error_family),
            "should_retry": bool(self.should_retry),
            "recommended_recovery_mode": str(self.recommended_recovery_mode),
            "recommended_backoff_seconds": int(self.recommended_backoff_seconds),
            "recommended_max_attempts": int(self.recommended_max_attempts),
            "cooldown_seconds": int(self.cooldown_seconds),
            "fallback_action_type": self.fallback_action_type,
            "should_open_operator_handoff": bool(self.should_open_operator_handoff),
            "should_quarantine_capability": bool(self.should_quarantine_capability),
            "confidence": float(self.confidence),
            "reason": str(self.reason),
            "context": self.context.to_dict(),
            "evidence_only": True,
            "must_not_issue_decision": True,
        }


@dataclass(frozen=True)
class RetryLearningSynthesis:
    context: RetryLearningContext
    report: FailurePatternReport
    dominant_pattern: FailurePattern | None


class RetryLearningEngine:
    """Evidence-only retry-learning advisor."""

    def __init__(
        self,
        *,
        learning_store: RetryLearningStore | None = None,
        error_family_classifier: ErrorFamilyClassifier | None = None,
        failure_pattern_detector: FailurePatternDetector | None = None,
        default_max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    ) -> None:
        self._learning_store = learning_store
        self._classifier = error_family_classifier or ErrorFamilyClassifier()
        self._pattern_detector = failure_pattern_detector or FailurePatternDetector()
        self._default_max_attempts = max(1, int(default_max_attempts))

    def _load_snapshot(self, *, tenant_id: str, action_type: str, error_family: str) -> RetryLearningSnapshot | None:
        if self._learning_store is None:
            return None
        return self._learning_store.load(
            tenant_id=_text(tenant_id or "default"),
            action_type=_text(action_type),
            error_family=_text(error_family or "unknown") or "unknown",
        )

    def _success_after_retry_rate(self, snapshot: RetryLearningSnapshot | None) -> float:
        if snapshot is None or snapshot.attempts <= 0:
            return 0.0
        return _clamp_unit(snapshot.successes_after_retry / float(snapshot.attempts))

    def _dominant_pattern(self, *, report: FailurePatternReport, action_type: str, error_family: str, capability: str, service_name: str) -> FailurePattern | None:
        scored: list[tuple[int, FailurePattern]] = []
        for pattern in report.patterns:
            if pattern.action_type != action_type or pattern.error_family != error_family:
                continue
            score = 0
            if capability and pattern.capability == capability:
                score += 4
            if service_name and pattern.service_name == service_name:
                score += 3
            score += pattern.total_failures + pattern.consecutive_failures + _severity_bonus(pattern.severity)
            scored.append((score, pattern))
        if scored:
            scored.sort(key=lambda item: item[0], reverse=True)
            return scored[0][1]
        fallback_scored: list[tuple[int, FailurePattern]] = []
        for pattern in report.patterns:
            if pattern.error_family != error_family:
                continue
            fallback_scored.append((pattern.total_failures + pattern.consecutive_failures + _severity_bonus(pattern.severity), pattern))
        if not fallback_scored:
            return None
        fallback_scored.sort(key=lambda item: item[0], reverse=True)
        return fallback_scored[0][1]

    def _build_synthesis(
        self,
        *,
        tenant_id: str,
        business_id: str,
        action_type: str,
        retry_kind: str,
        result_error: str | None,
        attempt_index: int,
        feedback: Mapping[str, Any] | None = None,
        recent_events: Iterable[Mapping[str, Any] | FailureEvent] = (),
        recovery_mode: str | None = None,
    ) -> RetryLearningSynthesis:
        body = _safe_dict(feedback)
        error_family = self._classifier.classify(result_error) or "unknown"
        capability = _text(body.get("capability") or body.get("capability_key"))
        service_name = _text(body.get("service_name") or body.get("service") or body.get("runner_name"))
        report = self._pattern_detector.detect(events=recent_events, tenant_id=_text(tenant_id), business_id=_text(business_id))
        dominant = self._dominant_pattern(report=report, action_type=_text(action_type), error_family=error_family, capability=capability, service_name=service_name)
        snapshot = self._load_snapshot(tenant_id=_text(tenant_id), action_type=_text(action_type), error_family=error_family)
        context = RetryLearningContext(
            tenant_id=_text(tenant_id),
            business_id=_text(business_id),
            action_type=_text(action_type),
            error_family=error_family,
            retry_kind=_text_lower(retry_kind),
            attempt_index=max(0, int(attempt_index)),
            result_error=_text(result_error),
            capability=capability,
            service_name=service_name,
            recovery_mode=_text(recovery_mode or body.get("recovery_mode")),
            blocked_by_policy=_safe_bool(body.get("blocked_by_policy")),
            approval_required=_safe_bool(body.get("approval_required")),
            operator_required=_safe_bool(body.get("operator_required")) or _safe_bool(body.get("approval_required")) or _text_lower(retry_kind) == "operator_required",
            learned_attempts=0 if snapshot is None else max(0, int(snapshot.attempts)),
            learned_success_after_retry_rate=self._success_after_retry_rate(snapshot),
            learned_last_backoff_seconds=0 if snapshot is None else max(0, int(snapshot.last_backoff_seconds)),
            recurring_pattern_count=max(0, int(report.recurring_pattern_count)),
            dominant_pattern_severity="low" if dominant is None else str(dominant.severity),
            dominant_pattern_failures=0 if dominant is None else max(0, int(dominant.total_failures)),
            dominant_pattern_should_cooldown=False if dominant is None else bool(dominant.should_cooldown),
            dominant_pattern_should_quarantine_capability=False if dominant is None else bool(dominant.should_quarantine_capability),
            evidence_only=True,
            must_not_issue_decision=True,
        )
        return RetryLearningSynthesis(context=context, report=report, dominant_pattern=dominant)

    def build_context(
        self,
        *,
        tenant_id: str,
        business_id: str,
        action_type: str,
        retry_kind: str,
        result_error: str | None,
        attempt_index: int,
        feedback: Mapping[str, Any] | None = None,
        recent_events: Iterable[Mapping[str, Any] | FailureEvent] = (),
        recovery_mode: str | None = None,
    ) -> RetryLearningContext:
        return self._build_synthesis(
            tenant_id=tenant_id,
            business_id=business_id,
            action_type=action_type,
            retry_kind=retry_kind,
            result_error=result_error,
            attempt_index=attempt_index,
            feedback=feedback,
            recent_events=recent_events,
            recovery_mode=recovery_mode,
        ).context

    def _confidence(self, *, context: RetryLearningContext, dominant_pattern: FailurePattern | None) -> float:
        confidence = 0.10
        if context.learned_attempts >= 3:
            confidence += 0.15
        if context.learned_attempts >= 8:
            confidence += 0.15
        if context.learned_success_after_retry_rate >= 0.50:
            confidence += 0.20
        elif context.learned_success_after_retry_rate >= 0.25:
            confidence += 0.10
        if dominant_pattern is not None and dominant_pattern.recurring:
            confidence += 0.10
        if dominant_pattern is not None and dominant_pattern.severity in {"high", "critical"}:
            confidence += 0.10
        if dominant_pattern is not None and dominant_pattern.total_failures >= 4:
            confidence += 0.10
        return _clamp_unit(confidence)

    def _base_backoff_and_mode(self, *, error_family: str, attempt_index: int, learned_last_backoff_seconds: int, learned_success_after_retry_rate: float) -> tuple[int, int, str]:
        family = _text_lower(error_family)
        attempt_no = max(0, int(attempt_index))
        if family == "rate_limit":
            backoff = max(30 * (attempt_no + 1), learned_last_backoff_seconds or 30)
            max_attempts = 2 if learned_success_after_retry_rate < 0.40 else 3
            return min(_MAX_RATE_LIMIT_BACKOFF_SECONDS, backoff), max_attempts, "backoff_retry"
        if family == "transport":
            backoff = max(10 * (attempt_no + 1), min(_MAX_TRANSPORT_BACKOFF_SECONDS, learned_last_backoff_seconds or 10))
            max_attempts = 2 if learned_success_after_retry_rate < 0.30 else 3
            return min(_MAX_TRANSPORT_BACKOFF_SECONDS, backoff), max_attempts, "transport_retry"
        backoff = max(5 * (attempt_no + 1), min(_MAX_GENERIC_BACKOFF_SECONDS, learned_last_backoff_seconds or 5))
        max_attempts = 2 if learned_success_after_retry_rate < 0.20 else self._default_max_attempts
        return min(_MAX_GENERIC_BACKOFF_SECONDS, backoff), max_attempts, "bounded_retry"

    def recommend(
        self,
        *,
        tenant_id: str,
        business_id: str,
        action_type: str,
        retry_kind: str,
        result_error: str | None,
        attempt_index: int,
        feedback: Mapping[str, Any] | None = None,
        recent_events: Iterable[Mapping[str, Any] | FailureEvent] = (),
        recovery_mode: str | None = None,
    ) -> RetryLearningRecommendation:
        synthesis = self._build_synthesis(
            tenant_id=tenant_id,
            business_id=business_id,
            action_type=action_type,
            retry_kind=retry_kind,
            result_error=result_error,
            attempt_index=attempt_index,
            feedback=feedback,
            recent_events=recent_events,
            recovery_mode=recovery_mode,
        )
        context = synthesis.context
        dominant = synthesis.dominant_pattern
        error_family = context.error_family
        confidence = self._confidence(context=context, dominant_pattern=dominant)
        if context.retry_kind == "success":
            return RetryLearningRecommendation(
                tenant_id=context.tenant_id,
                business_id=context.business_id,
                action_type=context.action_type,
                error_family=error_family,
                should_retry=False,
                recommended_recovery_mode="none",
                recommended_backoff_seconds=0,
                recommended_max_attempts=1,
                cooldown_seconds=0,
                fallback_action_type=None,
                should_open_operator_handoff=False,
                should_quarantine_capability=False,
                confidence=confidence,
                reason="execution_ok",
                context=context,
            )
        if context.blocked_by_policy or context.approval_required or context.operator_required:
            return RetryLearningRecommendation(
                tenant_id=context.tenant_id,
                business_id=context.business_id,
                action_type=context.action_type,
                error_family=error_family,
                should_retry=False,
                recommended_recovery_mode="operator_handoff",
                recommended_backoff_seconds=0,
                recommended_max_attempts=1,
                cooldown_seconds=0,
                fallback_action_type=None,
                should_open_operator_handoff=True,
                should_quarantine_capability=False,
                confidence=confidence,
                reason="operator_or_policy_gate",
                context=context,
            )
        if error_family in {"authorization", "validation"}:
            fallback_action_type = "notify_owner" if context.action_type != "notify_owner" else None
            return RetryLearningRecommendation(
                tenant_id=context.tenant_id,
                business_id=context.business_id,
                action_type=context.action_type,
                error_family=error_family,
                should_retry=False,
                recommended_recovery_mode="credential_recovery" if error_family == "authorization" else "stop",
                recommended_backoff_seconds=0,
                recommended_max_attempts=1,
                cooldown_seconds=0,
                fallback_action_type=fallback_action_type,
                should_open_operator_handoff=True,
                should_quarantine_capability=False,
                confidence=confidence,
                reason="non_retryable_failure_family",
                context=context,
            )
        recommended_backoff_seconds, recommended_max_attempts, recommended_recovery_mode = self._base_backoff_and_mode(
            error_family=error_family,
            attempt_index=context.attempt_index,
            learned_last_backoff_seconds=context.learned_last_backoff_seconds,
            learned_success_after_retry_rate=context.learned_success_after_retry_rate,
        )
        cooldown_seconds = 0
        should_open_operator_handoff = False
        should_quarantine_capability = False
        if error_family == 'rate_limit':
            reason = 'rate_limit_backoff'
        elif error_family == 'transport':
            reason = 'transient_transport_failure'
        else:
            reason = 'generic_recoverable_retry'
        if dominant is not None:
            recommended_backoff_seconds = max(recommended_backoff_seconds, max(0, int(dominant.recommended_backoff_floor_seconds)))
            recommended_max_attempts = min(max(1, int(recommended_max_attempts)), max(1, int(dominant.recommended_max_attempts)))
            cooldown_seconds = max(0, int(dominant.recommended_backoff_floor_seconds)) if dominant.should_cooldown else 0
            should_open_operator_handoff = bool(dominant.should_open_operator_handoff)
            should_quarantine_capability = bool(dominant.should_quarantine_capability)
            if dominant.severity == "critical" and dominant.success_after_retry_rate <= 0.15:
                recommended_recovery_mode = "cooldown_then_operator_review" if should_open_operator_handoff else "cooldown_retry"
                reason = "critical_recurring_failure_pattern"
            elif dominant.severity == "high":
                reason = "high_severity_failure_pattern"
            elif dominant.recurring:
                reason = "recurring_failure_pattern"
            if cooldown_seconds > 0 and should_open_operator_handoff:
                recommended_recovery_mode = "cooldown_then_operator_review"
            elif cooldown_seconds > 0 and recommended_recovery_mode in {"backoff_retry", "transport_retry", "bounded_retry"}:
                recommended_recovery_mode = "cooldown_retry"
        should_retry = context.attempt_index < recommended_max_attempts
        if should_quarantine_capability and not should_open_operator_handoff:
            should_open_operator_handoff = True
        if not should_retry and should_open_operator_handoff:
            fallback_action_type = "notify_owner" if context.action_type != "notify_owner" else None
            return RetryLearningRecommendation(
                tenant_id=context.tenant_id,
                business_id=context.business_id,
                action_type=context.action_type,
                error_family=error_family,
                should_retry=False,
                recommended_recovery_mode="operator_handoff",
                recommended_backoff_seconds=0,
                recommended_max_attempts=max(1, int(recommended_max_attempts)),
                cooldown_seconds=max(0, int(cooldown_seconds)),
                fallback_action_type=fallback_action_type,
                should_open_operator_handoff=True,
                should_quarantine_capability=bool(should_quarantine_capability),
                confidence=confidence,
                reason=reason,
                context=context,
            )
        return RetryLearningRecommendation(
            tenant_id=context.tenant_id,
            business_id=context.business_id,
            action_type=context.action_type,
            error_family=error_family,
            should_retry=bool(should_retry),
            recommended_recovery_mode=recommended_recovery_mode if should_retry else "stop",
            recommended_backoff_seconds=max(0, int(recommended_backoff_seconds if should_retry else 0)),
            recommended_max_attempts=max(1, int(recommended_max_attempts)),
            cooldown_seconds=max(0, int(cooldown_seconds)),
            fallback_action_type=None,
            should_open_operator_handoff=bool(should_open_operator_handoff),
            should_quarantine_capability=bool(should_quarantine_capability),
            confidence=confidence,
            reason=reason,
            context=context,
        )

    def record_outcome(
        self,
        *,
        tenant_id: str,
        action_type: str,
        retry_kind: str,
        result_error: str | None,
        backoff_seconds: int = 0,
        attempt_index: int | None = None,
    ) -> RetryLearningSnapshot | None:
        if self._learning_store is None:
            return None
        error_family = self._classifier.classify(result_error) or "unknown"
        tenant_key = _text(tenant_id or "default")
        action_key = _text(action_type)
        current = self._learning_store.load(tenant_id=tenant_key, action_type=action_key, error_family=error_family)
        updated = RetryLearningSnapshot(
            tenant_id=tenant_key,
            action_type=action_key,
            error_family=error_family,
            attempts=max(0, int(current.attempts)) + 1,
            successes_after_retry=max(0, int(current.successes_after_retry)) + int(_text_lower(retry_kind) == "success" and (attempt_index is None or int(attempt_index) > 0)),
            last_backoff_seconds=max(0, _safe_int(backoff_seconds)),
        )
        self._learning_store.save(updated)
        return updated

    def event_from_feedback(
        self,
        *,
        tenant_id: str,
        business_id: str,
        action_type: str,
        retry_kind: str,
        result_error: str | None,
        attempt_index: int,
        feedback: Mapping[str, Any] | None = None,
        recovery_mode: str | None = None,
    ) -> FailureEvent:
        return self._pattern_detector.event_from_feedback(
            tenant_id=tenant_id,
            business_id=business_id,
            action_type=action_type,
            retry_kind=retry_kind,
            result_error=result_error,
            attempt_index=attempt_index,
            feedback=feedback,
            recovery_mode=recovery_mode,
        )


__all__ = [
    "CANON_RETRY_LEARNING_ENGINE",
    "RETRY_LEARNING_SCHEMA_VERSION",
    "RetryLearningContext",
    "RetryLearningEngine",
    "RetryLearningRecommendation",
    "RetryLearningSynthesis",
]
