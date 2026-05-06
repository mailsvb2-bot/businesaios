from __future__ import annotations

from core.growth.ads.rl.action_space import build_action_space
from core.growth.ads.rl.contracts import AdsRLOptSpec


def test_action_space_caps_and_nonempty():
    spec = AdsRLOptSpec(
        platform="meta",
        campaign_id="c1",
        daily_budgets=[100.0, 200.0],
        bid_caps=[1.0, 2.0],
        cpa_targets=[10.0],
        creatives=["cr1", "cr2"],
        audiences=["a1"],
        objectives=["LEADS"],
        rollout_pct=5.0,
    )
    actions, st = build_action_space(spec, max_actions=3)
    assert actions
    assert st.n_actions == 3
    assert st.truncated is True
