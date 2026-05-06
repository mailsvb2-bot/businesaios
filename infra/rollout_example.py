from __future__ import annotations

from infra.rollout_models import RolloutRule
from infra.rollout_policy import RolloutPolicy


def example_rollout(subject_key: str) -> dict:
    policy = RolloutPolicy()
    decision = policy.evaluate(
        rule=RolloutRule(
            name="new_api_surface",
            percentage=25,
        ),
        subject_key=subject_key,
    )
    return {
        "rule_name": decision.rule_name,
        "enabled": decision.enabled,
        "bucket": decision.bucket,
    }
