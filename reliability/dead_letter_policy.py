from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from reliability.outbox_store import OutboxMessage


CANON_DEAD_LETTER_POLICY = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class DeadLetterDecision:
    move_to_dead_letter: bool
    reason: str
    retry_delay_seconds: int | None = None


@dataclass(frozen=True)
class DeadLetterPolicy:
    max_delivery_attempts: int = 5
    max_message_age_seconds: int = 86_400
    base_retry_delay_seconds: int = 30
    max_retry_delay_seconds: int = 3_600

    def classify(
        self,
        *,
        message: OutboxMessage,
        error: Exception | str,
        retryable: bool = True,
        now: datetime | None = None,
    ) -> DeadLetterDecision:
        del error
        message.validate()
        moment = now or utc_now()

        if not retryable:
            return DeadLetterDecision(move_to_dead_letter=True, reason="non_retryable_error", retry_delay_seconds=None)
        if int(message.delivery_attempts) >= int(self.max_delivery_attempts):
            return DeadLetterDecision(move_to_dead_letter=True, reason="max_attempts_exhausted", retry_delay_seconds=None)

        age_seconds = max(0, int((moment - message.created_at).total_seconds()))
        if age_seconds >= int(self.max_message_age_seconds):
            return DeadLetterDecision(move_to_dead_letter=True, reason="message_too_old", retry_delay_seconds=None)

        exponent = max(0, int(message.delivery_attempts))
        delay = min(
            int(self.max_retry_delay_seconds),
            int(self.base_retry_delay_seconds) * (2 ** exponent),
        )
        return DeadLetterDecision(move_to_dead_letter=False, reason="retry", retry_delay_seconds=max(1, delay))


__all__ = [
    "CANON_DEAD_LETTER_POLICY",
    "DeadLetterDecision",
    "DeadLetterPolicy",
]
