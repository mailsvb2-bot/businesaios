from __future__ import annotations

from growth.budget_engine import BudgetEngine
from growth.campaign_engine import CampaignEngine
from growth.creative_engine import CreativeEngine
from growth.engine_base import GrowthEngineSurface
from growth.core.growth_engine import CANON_GROWTH_CHANNEL_FEATURE_KEYS, GrowthEngine


def test_growth_engines_share_common_surface_base() -> None:
    assert issubclass(CampaignEngine, GrowthEngineSurface)
    assert issubclass(CreativeEngine, GrowthEngineSurface)
    assert issubclass(BudgetEngine, GrowthEngineSurface)


def test_growth_surface_artifact_contract_is_shared() -> None:
    payload = {"channel": "ads"}
    artifact = CampaignEngine().select_channel(payload)
    assert artifact == {"kind": "channel_selection", "payload": payload}


def test_growth_channel_bandit_contract_is_canonical() -> None:
    engine = GrowthEngine()
    left = {"intent_strength": 0.8, "historical_roas": 2.1, "urgency": 0.5, "expected_value": 120.0, "noise": 999.0}
    right = {"noise": -1.0, "expected_value": 120.0, "urgency": 0.5, "historical_roas": 2.1, "intent_strength": 0.8}
    assert tuple(engine._channel_bandit.feature_keys) == CANON_GROWTH_CHANNEL_FEATURE_KEYS
    assert engine._normalize_channel_context(left) == engine._normalize_channel_context(right)
