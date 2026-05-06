from __future__ import annotations

from dataclasses import dataclass


CANON_HEADLESS_RETRY_EXECUTOR_POLICY = True


@dataclass(frozen=True)
class RetryPlan:
    should_retry: bool
    next_attempt_index: int
    reason: str


@dataclass(frozen=True)
class RetryExecutorPolicy:
    """
    Bounded retry policy.

    Hard rules:
    - retries only recoverable failures
    - never retries operator_required
    - never retries beyond max_attempts
    - MUST NOT change business strategy
    """

    max_attempts: int = 2

    def evaluate(
        self,
        *,
        attempt_index: int,
        retry_kind: str,
        step_ok: bool,
    ) -> RetryPlan:
        if step_ok:
            return RetryPlan(
                should_retry=False,
                next_attempt_index=int(attempt_index),
                reason="step_ok",
            )

        if str(retry_kind) != "recoverable":
            return RetryPlan(
                should_retry=False,
                next_attempt_index=int(attempt_index),
                reason=f"not_retryable:{retry_kind}",
            )

        if int(attempt_index) + 1 >= int(self.max_attempts):
            return RetryPlan(
                should_retry=False,
                next_attempt_index=int(attempt_index),
                reason="retry_budget_exhausted",
            )

        return RetryPlan(
            should_retry=True,
            next_attempt_index=int(attempt_index) + 1,
            reason="recoverable_retry",
        )


__all__ = [
    "CANON_HEADLESS_RETRY_EXECUTOR_POLICY",
    "RetryExecutorPolicy",
    "RetryPlan",
]
