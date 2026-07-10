from __future__ import annotations

import pytest

from connectors.platform.connector_retry_policy import (
    ConnectorRetryPolicy,
    ConnectorRetryRule,
    RetryClassification,
    RetryContext,
)
from interfaces.common.connector_result import ConnectorResult


def test_retry_rule_validation_normalization_and_matching() -> None:
    rule = ConnectorRetryRule(
        operation=" sync ",
        max_attempts=4,
        retryable_result_codes=("timeout", "timeout", "", "rate_limited"),
        non_retryable_result_codes=("forbidden", "", "forbidden"),
    )

    assert rule.operation == "sync"
    assert rule.retryable_result_codes == ("rate_limited", "timeout")
    assert rule.non_retryable_result_codes == ("forbidden",)
    assert rule.matches("sync")
    assert not rule.matches("other")
    assert ConnectorRetryRule().matches("anything")

    with pytest.raises(ValueError, match="max_attempts must be > 0"):
        ConnectorRetryRule(max_attempts=0)

    with pytest.raises(ValueError, match="base_delay_seconds must be >= 0"):
        ConnectorRetryRule(base_delay_seconds=-1)

    with pytest.raises(ValueError, match="max_delay_seconds must be >= 0"):
        ConnectorRetryRule(max_delay_seconds=-1)

    with pytest.raises(ValueError, match="base_delay_seconds must be <= max_delay_seconds"):
        ConnectorRetryRule(base_delay_seconds=2, max_delay_seconds=1)

    with pytest.raises(ValueError, match="jitter_ratio must be >= 0"):
        ConnectorRetryRule(jitter_ratio=-0.1)


def test_resolve_rule_prefers_specific_rule_and_supports_register() -> None:
    default = ConnectorRetryRule(max_attempts=9)
    wildcard = ConnectorRetryRule(operation="*", max_attempts=7)
    specific = ConnectorRetryRule(operation="sync", max_attempts=2)

    policy = ConnectorRetryPolicy(
        default_rule=default,
        rules=(wildcard, specific),
    )

    assert policy.resolve_rule(operation="sync") is specific
    assert policy.resolve_rule(operation="other") is wildcard

    export_rule = ConnectorRetryRule(operation="export", max_attempts=5)
    policy.register(export_rule)

    assert policy.resolve_rule(operation="export") is export_rule

    with pytest.raises(ValueError, match="operation is required"):
        policy.resolve_rule(operation=" ")


def test_classify_result_success_non_retryable_retryable_and_exhausted() -> None:
    policy = ConnectorRetryPolicy(
        default_rule=ConnectorRetryRule(
            max_attempts=3,
            base_delay_seconds=0.5,
            max_delay_seconds=4,
            jitter_ratio=0,
        )
    )
    context = RetryContext(operation="read")

    success = policy.classify_result(
        context=context,
        result=ConnectorResult(ok=True, code="ok"),
        attempt=1,
    )
    assert success.retryable is False
    assert success.terminal is True
    assert success.reason == "success"
    assert success.delay_seconds is None
    assert success.metadata["idempotent"] is True

    forbidden = policy.classify_result(
        context=context,
        result=ConnectorResult(ok=False, code="forbidden"),
        attempt=1,
    )
    assert forbidden.retryable is False
    assert forbidden.terminal is True
    assert forbidden.reason == "non_retryable_result"

    retryable = policy.classify_result(
        context=context,
        result=ConnectorResult(
            ok=False,
            code="timeout",
            payload={"retry_after_seconds": 1.75},
        ),
        attempt=1,
    )
    assert retryable.retryable is True
    assert retryable.terminal is False
    assert retryable.reason == "retryable_result"
    assert retryable.delay_seconds == 1.75

    exhausted = policy.classify_result(
        context=context,
        result=ConnectorResult(ok=False, code="timeout"),
        attempt=3,
    )
    assert exhausted.retryable is False
    assert exhausted.terminal is True
    assert exhausted.reason == "retry_exhausted"
    assert exhausted.delay_seconds is None

    message_retry = policy.classify_result(
        context=context,
        result=ConnectorResult(
            ok=False,
            code="unknown",
            message="Please retry later",
        ),
        attempt=1,
    )
    assert message_retry.retryable is True
    assert message_retry.reason == "retryable_result"


def test_non_idempotent_write_is_blocked_unless_rule_allows_it() -> None:
    unsafe_context = RetryContext(
        operation="write",
        write=True,
        idempotent=False,
    )

    blocked_policy = ConnectorRetryPolicy(
        default_rule=ConnectorRetryRule(
            max_attempts=3,
            jitter_ratio=0,
        )
    )
    blocked = blocked_policy.classify_result(
        context=unsafe_context,
        result=ConnectorResult(ok=False, code="timeout"),
        attempt=1,
    )

    assert blocked.retryable is False
    assert blocked.terminal is True
    assert blocked.reason == "unsafe_non_idempotent_write"
    assert blocked.metadata["idempotent"] is False

    allowed_policy = ConnectorRetryPolicy(
        default_rule=ConnectorRetryRule(
            max_attempts=3,
            jitter_ratio=0,
            allow_retries_for_non_idempotent_write=True,
        )
    )
    allowed = allowed_policy.classify_result(
        context=unsafe_context,
        result=ConnectorResult(ok=False, code="timeout"),
        attempt=1,
    )

    assert allowed.retryable is True
    assert allowed.terminal is False
    assert allowed.reason == "retryable_result"


class RateLimitError(Exception):
    def __init__(self, retry_after_s: object) -> None:
        super().__init__("rate limited")
        self.retry_after_s = retry_after_s


class TemporaryConnectionError(Exception):
    pass


class StatusError(Exception):
    def __init__(self, status: int) -> None:
        super().__init__(f"status={status}")
        self.status = status


def test_classify_exception_categories_retry_after_and_terminal_paths() -> None:
    policy = ConnectorRetryPolicy(
        default_rule=ConnectorRetryRule(
            max_attempts=3,
            base_delay_seconds=0.5,
            max_delay_seconds=4,
            jitter_ratio=0,
        )
    )
    context = RetryContext(operation="read")

    timeout = policy.classify_exception(
        context=context,
        error=TimeoutError("timeout"),
        attempt=1,
    )
    assert timeout.retryable is True
    assert timeout.reason == "timeout"
    assert timeout.delay_seconds == 0.5

    rate_limited = policy.classify_exception(
        context=context,
        error=RateLimitError(2.25),
        attempt=1,
    )
    assert rate_limited.retryable is True
    assert rate_limited.reason == "rate_limited"
    assert rate_limited.delay_seconds == 2.25

    bad_retry_after = policy.classify_exception(
        context=context,
        error=RateLimitError("bad"),
        attempt=2,
    )
    assert bad_retry_after.retryable is True
    assert bad_retry_after.delay_seconds == 1.0

    transport = policy.classify_exception(
        context=context,
        error=TemporaryConnectionError("temporary"),
        attempt=1,
    )
    assert transport.retryable is True
    assert transport.reason == "transport_error"

    upstream = policy.classify_exception(
        context=context,
        error=StatusError(503),
        attempt=1,
    )
    assert upstream.retryable is True
    assert upstream.reason == "upstream_5xx"

    generic = policy.classify_exception(
        context=context,
        error=ValueError("bad input"),
        attempt=1,
    )
    assert generic.retryable is False
    assert generic.terminal is True
    assert generic.reason == "exception"

    exhausted = policy.classify_exception(
        context=context,
        error=TimeoutError("timeout"),
        attempt=3,
    )
    assert exhausted.retryable is False
    assert exhausted.terminal is True
    assert exhausted.reason == "retry_exhausted"


def test_exception_retry_respects_non_idempotent_write_safety() -> None:
    policy = ConnectorRetryPolicy(
        default_rule=ConnectorRetryRule(
            max_attempts=3,
            jitter_ratio=0,
        )
    )
    context = RetryContext(
        operation="write",
        write=True,
        idempotent=False,
    )

    result = policy.classify_exception(
        context=context,
        error=TimeoutError("timeout"),
        attempt=1,
    )

    assert result.retryable is False
    assert result.terminal is True
    assert result.reason == "unsafe_non_idempotent_write"


def test_delay_jitter_caps_base_and_maybe_sleep() -> None:
    sleeps: list[float] = []

    policy = ConnectorRetryPolicy(
        default_rule=ConnectorRetryRule(
            max_attempts=5,
            base_delay_seconds=0.5,
            max_delay_seconds=2,
            jitter_ratio=0.5,
        ),
        random_fn=lambda: 1.0,
        sleep_fn=sleeps.append,
    )

    assert policy.delay_for_attempt(attempt=1, operation="read") == pytest.approx(0.75)
    assert policy.delay_for_attempt(attempt=3, operation="read") == pytest.approx(3.0)

    delayed = RetryClassification(
        retryable=True,
        reason="retryable_result",
        delay_seconds=1.25,
        terminal=False,
        attempt=1,
        max_attempts=3,
    )
    policy.maybe_sleep(delayed)
    assert sleeps == [1.25]

    policy.maybe_sleep(
        RetryClassification(
            retryable=False,
            reason="terminal",
            delay_seconds=None,
            terminal=True,
            attempt=3,
            max_attempts=3,
        )
    )
    policy.maybe_sleep(
        RetryClassification(
            retryable=True,
            reason="zero",
            delay_seconds=0,
            terminal=False,
            attempt=1,
            max_attempts=3,
        )
    )

    assert sleeps == [1.25]


def test_retry_after_payload_normalization() -> None:
    policy = ConnectorRetryPolicy()

    assert policy._result_retry_after(
        ConnectorResult(
            ok=False,
            code="timeout",
            payload={"retry_after_s": -5},
        )
    ) == 0.0

    assert policy._result_retry_after(
        ConnectorResult(
            ok=False,
            code="timeout",
            payload={"retry_after_seconds": "bad"},
        )
    ) is None

    assert policy._result_retry_after(
        ConnectorResult(ok=False, code="timeout")
    ) is None
