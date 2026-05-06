from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Callable, Mapping

from interfaces.common.connector_result import ConnectorResult

CANON_CONNECTOR_RETRY_POLICY = True


@dataclass(frozen=True)
class ConnectorRetryRule:
    operation: str = '*'
    max_attempts: int = 3
    base_delay_seconds: float = 0.25
    max_delay_seconds: float = 5.0
    jitter_ratio: float = 0.15
    allow_retries_for_non_idempotent_write: bool = False
    retryable_result_codes: tuple[str, ...] = (
        'timeout', 'transport_error', 'temporarily_unavailable', 'upstream_5xx', 'rate_limited', 'throttled',
        'connector_unavailable', 'verify_failed_transient',
    )
    non_retryable_result_codes: tuple[str, ...] = (
        'invalid_request', 'invalid_credentials', 'forbidden', 'not_found', 'validation_error', 'approval_required',
        'quota_exhausted', 'human_review_required', 'policy_denied', 'unsupported_operation',
    )

    def __post_init__(self) -> None:
        if int(self.max_attempts) <= 0:
            raise ValueError('max_attempts must be > 0')
        if float(self.base_delay_seconds) < 0:
            raise ValueError('base_delay_seconds must be >= 0')
        if float(self.max_delay_seconds) < 0:
            raise ValueError('max_delay_seconds must be >= 0')
        if float(self.base_delay_seconds) > float(self.max_delay_seconds):
            raise ValueError('base_delay_seconds must be <= max_delay_seconds')
        if float(self.jitter_ratio) < 0:
            raise ValueError('jitter_ratio must be >= 0')
        object.__setattr__(self, 'operation', str(self.operation or '*').strip() or '*')
        object.__setattr__(self, 'retryable_result_codes', tuple(sorted({str(x).strip() for x in self.retryable_result_codes if str(x).strip()})))
        object.__setattr__(self, 'non_retryable_result_codes', tuple(sorted({str(x).strip() for x in self.non_retryable_result_codes if str(x).strip()})))

    def matches(self, operation: str) -> bool:
        op = str(operation or '').strip()
        return self.operation == '*' or self.operation == op


@dataclass(frozen=True)
class RetryContext:
    operation: str
    write: bool = False
    verify: bool = False
    dry_run: bool = False
    idempotency_key_present: bool = False
    idempotent: bool | None = None


@dataclass(frozen=True)
class RetryClassification:
    retryable: bool
    reason: str
    delay_seconds: float | None
    terminal: bool
    attempt: int
    max_attempts: int
    metadata: Mapping[str, object] = field(default_factory=dict)


class ConnectorRetryPolicy:
    def __init__(self, *, default_rule: ConnectorRetryRule | None = None, rules: tuple[ConnectorRetryRule, ...] = (), random_fn: Callable[[], float] | None = None, sleep_fn: Callable[[float], None] | None = None) -> None:
        self._default_rule = default_rule or ConnectorRetryRule()
        self._rules = list(rules)
        self._random = random_fn or random.random
        self._sleep = sleep_fn or time.sleep

    def register(self, rule: ConnectorRetryRule) -> None:
        self._rules.append(rule)

    def resolve_rule(self, *, operation: str) -> ConnectorRetryRule:
        op = str(operation or '').strip()
        if not op:
            raise ValueError('operation is required')
        matches = [rule for rule in self._rules if rule.matches(op)]
        if matches:
            matches.sort(key=lambda item: (0 if item.operation != '*' else 1,))
            return matches[0]
        return self._default_rule

    def classify_result(self, *, context: RetryContext, result: ConnectorResult, attempt: int) -> RetryClassification:
        rule = self.resolve_rule(operation=context.operation)
        code = str(getattr(result, 'code', '') or '').strip().lower()
        if bool(getattr(result, 'ok', False)):
            return RetryClassification(False, 'success', None, True, int(attempt), int(rule.max_attempts), {'code': code, 'idempotent': self._context_is_idempotent(context)})
        if code in set(rule.non_retryable_result_codes):
            return RetryClassification(False, 'non_retryable_result', None, True, int(attempt), int(rule.max_attempts), {'code': code})
        retryable = code in set(rule.retryable_result_codes) or code.startswith('retry_') or 'retry' in str(getattr(result, 'message', '') or '').lower()
        reason = 'retryable_result' if retryable else 'result_error'
        if retryable and not self._safe_to_retry(context=context, rule=rule):
            retryable = False
            reason = 'unsafe_non_idempotent_write'
        delay = self._result_retry_after(result) if retryable else None
        if delay is None and retryable:
            delay = self.delay_for_attempt(attempt=attempt, operation=context.operation)
        terminal = (not retryable) or int(attempt) >= int(rule.max_attempts)
        return RetryClassification(retryable and not terminal, reason if not terminal else ('retry_exhausted' if retryable else reason), None if terminal else delay, terminal, int(attempt), int(rule.max_attempts), {'code': code, 'idempotent': self._context_is_idempotent(context)})

    def classify_exception(self, *, context: RetryContext, error: BaseException, attempt: int) -> RetryClassification:
        rule = self.resolve_rule(operation=context.operation)
        kind = error.__class__.__name__.lower()
        status = getattr(error, 'status', None)
        retry_after = getattr(error, 'retry_after_s', None)
        retryable = False
        reason = 'exception'
        if 'timeout' in kind:
            retryable, reason = True, 'timeout'
        elif 'ratelimit' in kind or 'throttle' in kind:
            retryable, reason = True, 'rate_limited'
        elif 'transport' in kind or 'connection' in kind or 'temporary' in kind:
            retryable, reason = True, 'transport_error'
        elif isinstance(status, int) and (status == 429 or status >= 500):
            retryable, reason = True, 'upstream_5xx'
        if retryable and not self._safe_to_retry(context=context, rule=rule):
            retryable = False
            reason = 'unsafe_non_idempotent_write'
        delay = None
        if retryable:
            if retry_after is not None:
                try:
                    delay = max(0.0, float(retry_after))
                except Exception:
                    delay = None
            if delay is None:
                delay = self.delay_for_attempt(attempt=attempt, operation=context.operation)
        terminal = (not retryable) or int(attempt) >= int(rule.max_attempts)
        return RetryClassification(retryable and not terminal, reason if not terminal else ('retry_exhausted' if retryable else reason), None if terminal else delay, terminal, int(attempt), int(rule.max_attempts), {'exception_type': error.__class__.__name__, 'idempotent': self._context_is_idempotent(context)})

    def delay_for_attempt(self, *, attempt: int, operation: str) -> float:
        rule = self.resolve_rule(operation=operation)
        base = min(float(rule.max_delay_seconds), float(rule.base_delay_seconds) * (2 ** max(0, int(attempt) - 1)))
        if base <= 0:
            return 0.0
        jitter = base * float(rule.jitter_ratio)
        if jitter <= 0:
            return base
        offset = (self._random() * 2.0 - 1.0) * jitter
        return max(0.0, base + offset)

    def maybe_sleep(self, classification: RetryClassification) -> None:
        if classification.delay_seconds is None or float(classification.delay_seconds) <= 0:
            return
        self._sleep(float(classification.delay_seconds))

    def _context_is_idempotent(self, context: RetryContext) -> bool:
        if context.idempotent is not None:
            return bool(context.idempotent)
        return bool(context.dry_run or context.idempotency_key_present or not context.write)

    def _safe_to_retry(self, *, context: RetryContext, rule: ConnectorRetryRule) -> bool:
        if not context.write:
            return True
        if self._context_is_idempotent(context):
            return True
        return bool(rule.allow_retries_for_non_idempotent_write)

    def _result_retry_after(self, result: ConnectorResult) -> float | None:
        payload = getattr(result, 'payload', {}) or {}
        if isinstance(payload, dict):
            candidate = payload.get('retry_after_seconds', payload.get('retry_after_s'))
            if candidate is not None:
                try:
                    return max(0.0, float(candidate))
                except Exception:
                    return None
        return None


__all__ = ['CANON_CONNECTOR_RETRY_POLICY', 'ConnectorRetryPolicy', 'ConnectorRetryRule', 'RetryClassification', 'RetryContext']
