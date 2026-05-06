from __future__ import annotations

import hashlib
from dataclasses import dataclass

from infra.rollout_models import RolloutDecision, RolloutRule


@dataclass(frozen=True)
class RolloutPolicy:
    def evaluate(self, *, rule: RolloutRule, subject_key: str) -> RolloutDecision:
        if rule.percentage < 0 or rule.percentage > 100:
            raise ValueError("Rollout percentage must be between 0 and 100.")

        bucket = _stable_bucket(subject_key)
        enabled = bucket < rule.percentage
        return RolloutDecision(
            rule_name=rule.name,
            enabled=enabled,
            bucket=bucket,
        )


def _stable_bucket(subject_key: str) -> int:
    digest = hashlib.sha256(subject_key.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100
