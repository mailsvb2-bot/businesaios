from __future__ import annotations

from dataclasses import dataclass


CANON_REENCRYPTION_FAILURE_POLICY = True


@dataclass(frozen=True)
class ReencryptionFailureDecision:
    action: str
    reason: str


class ReencryptionFailurePolicy:
    """Fail-closed policy for bulk secret reencryption."""

    def evaluate(self, *, processed_count: int, failed_count: int, consecutive_failures: int) -> ReencryptionFailureDecision:
        if int(consecutive_failures) >= 3:
            return ReencryptionFailureDecision(action='pause_job', reason='too_many_consecutive_failures')
        if int(failed_count) > int(processed_count) and int(failed_count) >= 5:
            return ReencryptionFailureDecision(action='pause_job', reason='failure_ratio_too_high')
        return ReencryptionFailureDecision(action='continue', reason='within_failure_budget')
    decide = evaluate


__all__ = [
    'CANON_REENCRYPTION_FAILURE_POLICY',
    'ReencryptionFailureDecision',
    'ReencryptionFailurePolicy',
]
