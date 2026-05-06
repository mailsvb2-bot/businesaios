from __future__ import annotations

import pytest

from core.ads.autopilot.contract import AdsAutopilotConstraints, AdsAutopilotRequest
from core.ads.autopilot.engine import AdsAutopilotEngine


class _Ads:
    def metrics(self, tenant_id, scope):
        return {"spend_minor": 0, "conversions": 0, "revenue_minor": 0}

    def build_plan(self, tenant_id, spec):
        class _Plan:
            commands = []
            notes = "ok"
        return _Plan()


class _Builder:
    def build(self, **kwargs):
        class _Built:
            spec = {}
            notes = "ok"
        return _Built()


def test_ads_autopilot_engine_rejects_direct_apply_request() -> None:
    engine = AdsAutopilotEngine(ads=_Ads(), builder=_Builder())
    req = AdsAutopilotRequest(
        tenant_id="t1",
        constraints=AdsAutopilotConstraints(),
        dry_run=False,
        plan_only=False,
        apply_enabled=True,
        decision_id="d1",
        correlation_id="c1",
        issuer_id="businesaios-core",
        issued_action="ads_autopilot_tick@v1",
        route="DecisionCore->RuntimeExecutor->AdsAutopilotHandler",
    )

    with pytest.raises(ValueError, match="forbids direct apply"):
        engine.tick(req)