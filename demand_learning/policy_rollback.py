from __future__ import annotations

from config.learning_thresholds import (
    MIN_REPLAY_SAMPLE_SIZE,
    POLICY_ROLLBACK_MAX_CONVERSION_RATE,
    POLICY_ROLLBACK_MIN_BAD_OUTCOME_RATE,
)
from shared.numbers import coerce_float, coerce_int


class PolicyRollback:
    def allow(self, replay_metrics: dict[str, float]) -> bool:
        sample_size = coerce_int(replay_metrics.get('sample_size'), 0, minimum=0)
        conversion_rate = coerce_float(replay_metrics.get('offline_conversion_rate'), 0.0, minimum=0.0, maximum=1.0)
        bad_outcome_rate = coerce_float(replay_metrics.get('offline_bad_outcome_rate'), 0.0, minimum=0.0, maximum=1.0)
        return sample_size >= MIN_REPLAY_SAMPLE_SIZE and (
            conversion_rate < POLICY_ROLLBACK_MAX_CONVERSION_RATE or bad_outcome_rate >= POLICY_ROLLBACK_MIN_BAD_OUTCOME_RATE
        )
