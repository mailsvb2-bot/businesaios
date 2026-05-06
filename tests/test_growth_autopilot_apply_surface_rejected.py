from __future__ import annotations

import pytest

from core.growth.autopilot_config import AutopilotRunConfig
from core.growth.autopilot_engine import AutopilotEngine


class _Sink:
    def emit(self, **kwargs):
        return None


class _Gateway:
    def propose(self, **kwargs):
        return "p1"


class _Apply:
    def apply(self, **kwargs):
        return None


def test_growth_autopilot_rejects_direct_apply_surface() -> None:
    engine = AutopilotEngine(
        entitlements_provider=object(),
        ads_service=object(),
        ads_reco_service=object(),
        ads_apply_service=_Apply(),
        trust_score=object(),
        circuit_breaker=object(),
        sink=_Sink(),
        cfg=AutopilotRunConfig(),
        proposal_gateway=_Gateway(),
    )

    with pytest.raises(RuntimeError, match="must not be wired with direct ads apply surface"):
        engine._ensure_guarded_execution_contract()
