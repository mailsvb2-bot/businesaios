from __future__ import annotations

import pytest

from core.tenancy.normalization import normalize_tenant_id, require_tenant_id
from runtime.handlers.pricing_select import handle_pricing_select
from runtime.messaging.inbound_message import InboundMessage
from runtime.messaging.router import UnifiedConversationRouter
from runtime.jobs.ads_autopilot_tick import ads_autopilot_tick


class _Effects:
    def __init__(self):
        self.calls = []

    def send_message(self, **kwargs):
        self.calls.append(kwargs)
        return kwargs


def test_tenant_normalization_rejects_placeholder_default():
    assert normalize_tenant_id("default") == ""
    with pytest.raises(ValueError):
        require_tenant_id("default")


def test_pricing_route_violation_keeps_safe_message_and_ids():
    effects = _Effects()
    env = type("Env", (), {"decision": type("D", (), {"decision_id": "d1", "correlation_id": "c1"})()})()
    out = handle_pricing_select({"user_id": "u1"}, effects, env, selection_service=None)
    assert out["decision_id"] == "d1"
    assert out["correlation_id"] == "c1"
    assert "route contract" in out["text"].lower()
    assert out["track_payload"]["error"] == "DecisionRouteViolation"


def test_inbound_message_requires_real_tenant():
    with pytest.raises(ValueError):
        InboundMessage(tenant_id="default", channel="telegram", user_id="u1")


def test_router_requires_real_tenant():
    router = UnifiedConversationRouter()
    with pytest.raises(ValueError):
        router.normalize(channel="telegram", tenant_id="default", payload={"user_id": "u1"})


class _Registry:
    def list_active_tenants(self):
        return [type("T", (), {"tenant_id": "default"})(), type("T", (), {"tenant_id": "tenant-1"})()]


class _TokenStore:
    async def list_connected_accounts(self, tenant_id: str):
        return [type("A", (), {"platform": "meta", "account_id": "acc1"})()]


class _Scheduler:
    def __init__(self):
        self.targets = []

    async def tick(self, target):
        self.targets.append(target)


@pytest.mark.asyncio
async def test_ads_autopilot_tick_skips_placeholder_default_tenant():
    scheduler = _Scheduler()
    sys = type("Sys", (), {"autopilot_scheduler": scheduler, "tenant_registry": _Registry(), "ads_tokens": _TokenStore(), "default_tenant_id": "default"})()
    await ads_autopilot_tick(sys)
    assert [t.tenant_id for t in scheduler.targets] == ["tenant-1"]
