from __future__ import annotations

import pytest

from core.ads.autopilot.contract import AdsAutopilotConstraints, AdsAutopilotRequest
from core.ads.autopilot.engine import AdsAutopilotEngine


class _PlanCmd:
    def __init__(self):
        self.platform = "tg"
        self.action = "create_campaign"
        self.payload = {"name": "x"}


class _Plan:
    def __init__(self):
        self.commands = [_PlanCmd()]
        self.notes = "ok"


class _Ads:
    def __init__(self):
        self.apply_calls = 0

    def metrics(self, tenant_id, scope):
        return {"spend_minor": 100, "roas_x1000": 2000}

    def build_plan(self, tenant_id, spec):
        return _Plan()

    def apply_plan(self, tenant_id, plan):
        self.apply_calls += 1
        return {"status": "applied"}


class _Built:
    def __init__(self):
        self.spec = {"goal": "leads"}
        self.notes = "built"


class _Builder:
    def build(self, **kwargs):
        return _Built()


def _req(**overrides):
    base = dict(tenant_id="t1", objective="leads", constraints=AdsAutopilotConstraints(currency="RUB"), dry_run=True, plan_only=True, apply_enabled=False, decision_id="d1", correlation_id="c1", issuer_id="businesaios-core", issued_action="ads_autopilot_tick@v1", route="DecisionCore->RuntimeExecutor->AdsAutopilotHandler")
    base.update(overrides)
    return AdsAutopilotRequest(**base)


def test_ads_autopilot_tick_builds_plan_without_direct_apply():
    ads = _Ads()
    engine = AdsAutopilotEngine(ads=ads, builder=_Builder())
    res = engine.tick(_req())
    assert res.status == "ok"
    assert res.applied["status"] == "skipped"
    assert ads.apply_calls == 0


def test_ads_autopilot_tick_still_refuses_direct_apply_even_if_requested():
    ads = _Ads()
    engine = AdsAutopilotEngine(ads=ads, builder=_Builder())
    res = engine.tick(_req(dry_run=False, plan_only=False, apply_enabled=True))
    assert res.status == "ok"
    assert ads.apply_calls == 0
    assert res.applied["reason"] == "direct_apply_forbidden_use_ads_apply_execute"


def test_ads_autopilot_tick_requires_decisioncore_route():
    ads = _Ads()
    engine = AdsAutopilotEngine(ads=ads, builder=_Builder())
    with pytest.raises(ValueError, match="issuer_id"):
        engine.tick(_req(issuer_id="other-brain"))