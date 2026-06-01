from __future__ import annotations

from core.growth.ads.rl.experience_store import RLStep
from core.growth.ads.rl.off_policy import (
    doubly_robust_for_deterministic_target,
    ips_for_deterministic_target,
    snips_for_deterministic_target,
)


def test_ope_estimators_basic():
    steps = [
        RLStep(ts_ms=1, policy_id="p", campaign_id="c", platform="meta", action_key="a", action={}, reward=1.0, reward_mode="profit", meta={"propensity": 0.5}),
        RLStep(ts_ms=2, policy_id="p", campaign_id="c", platform="meta", action_key="b", action={}, reward=3.0, reward_mode="profit", meta={"propensity": 0.5}),
        RLStep(ts_ms=3, policy_id="p", campaign_id="c", platform="meta", action_key="a", action={}, reward=2.0, reward_mode="profit", meta={"propensity": 0.25}),
    ]
    ips = ips_for_deterministic_target(steps=steps, target_action_key="a")
    snips = snips_for_deterministic_target(steps=steps, target_action_key="a")
    dr = doubly_robust_for_deterministic_target(steps=steps, target_action_key="a", qhat=1.5)

    assert ips.n == 3
    assert snips.n == 3
    assert dr.n == 3

    # IPS: (1/0.5 +2/0.25) / 3 = (2 +8) / 3 = 3.333...
    assert abs(ips.value - (10.0 / 3.0)) < 1e-6
    # SNIPS: weights only on matching actions: w=2,4 => (2*1+4*2)/(2+4)=10/6=1.666...
    assert abs(snips.value - (10.0 / 6.0)) < 1e-6
    assert isinstance(dr.value, float)
