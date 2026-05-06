from core.policies.types import PolicyRef, RolloutConfig
from core.policies.registry import PolicyRegistry
from core.policies.rollout import SafeRolloutManager


def test_promote_flow():
    registry = PolicyRegistry()
    cfg = RolloutConfig(canary_pct=0.5, min_decisions=5, max_error_rate=0.2)

    active = PolicyRef("A", "1")
    canary = PolicyRef("B", "1")

    registry.promote(active)

    rollout = SafeRolloutManager(registry, cfg)
    rollout.start_canary(canary)

    for _ in range(5):
        rollout.record_decision(error=False)

    assert rollout.tick() == "promote"
    assert registry.active().policy_id == "B"


def test_rollback_flow():
    registry = PolicyRegistry()
    cfg = RolloutConfig(canary_pct=0.5, min_decisions=5, max_error_rate=0.2)

    active = PolicyRef("A", "1")
    canary = PolicyRef("B", "1")

    registry.promote(active)

    rollout = SafeRolloutManager(registry, cfg)
    rollout.start_canary(canary)

    for _ in range(5):
        rollout.record_decision(error=True)

    assert rollout.tick() == "rollback"
    assert registry.active().policy_id == "A"
