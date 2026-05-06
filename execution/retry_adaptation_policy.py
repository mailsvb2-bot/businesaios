from __future__ import annotations

from dataclasses import dataclass

from execution.error_family_classifier import ErrorFamilyClassifier
from application.learning.retry_learning_store import RetryLearningSnapshot


CANON_RETRY_ADAPTATION_POLICY = True


@dataclass(frozen=True)
class RetryAdaptationView:
    should_retry: bool
    backoff_seconds: int
    recovery_mode: str
    reason: str
    fallback_action_type: str | None = None


class RetryAdaptationPolicy:
    def __init__(self) -> None:
        self._classifier = ErrorFamilyClassifier()

    def evaluate(self, *, action_type: str, retry_kind: str, result_error: str | None, attempt_index: int, learning_snapshot: RetryLearningSnapshot | None = None) -> RetryAdaptationView:
        error_family = self._classifier.classify(result_error)
        learned_backoff = 0 if learning_snapshot is None else int(learning_snapshot.last_backoff_seconds)
        if retry_kind == 'success':
            return RetryAdaptationView(False, 0, 'none', 'execution_ok')
        if retry_kind != 'recoverable':
            fallback = 'notify_owner' if action_type != 'notify_owner' else None
            return RetryAdaptationView(False, 0, 'safe_fallback' if fallback else 'stop', error_family or 'non_recoverable_error', fallback)
        if error_family == 'rate_limit':
            return RetryAdaptationView(True, max(30 * (int(attempt_index) + 1), learned_backoff), 'backoff_retry', 'rate_limit_backoff')
        if error_family == 'transport':
            return RetryAdaptationView(True, max(10 * (int(attempt_index) + 1), min(120, learned_backoff or 10)), 'transport_retry', 'transient_transport_failure')
        if error_family == 'authorization':
            fallback = 'notify_owner' if action_type != 'notify_owner' else None
            return RetryAdaptationView(False, 0, 'credential_recovery' if fallback else 'stop', 'authorization_recovery_required', fallback)
        return RetryAdaptationView(True, max(5 * (int(attempt_index) + 1), min(60, learned_backoff or 5)), 'bounded_retry', 'generic_recoverable_retry')


__all__ = ['CANON_RETRY_ADAPTATION_POLICY', 'RetryAdaptationPolicy', 'RetryAdaptationView']
