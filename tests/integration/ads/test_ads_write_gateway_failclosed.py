"""Canonical ads gateway does not report success when an operation fails."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from bootstrap.ads_write_gateway import AdsWriteGateway, AdsWriteRequest


def gateway(connector=None):
    return AdsWriteGateway(
        registry=SimpleNamespace(get_optional=lambda platform: connector),
        guardrails=SimpleNamespace(allow_apply=lambda **kwargs: True),
        circuit_breaker=SimpleNamespace(allow=lambda **kwargs: True),
        sink=SimpleNamespace(emit=Mock()),
        writes_enabled=True,
    )


@pytest.mark.asyncio
async def test_unregistered_provider_does_not_raise_or_claim_success():
    result = await gateway().apply_plan(AdsWriteRequest(
        tenant_id="t", platform="yandex_direct",
        plan={"ops": [{"account_id": "a", "object_type": "ad", "payload": {"name": "x"}}]},
    ))
    assert result == {"status": "skipped", "reason": "connector_not_configured", "platform": "yandex_direct"}


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_result", [
    {"status": "failed", "reason": "provider_rejected"},
    {"status": "error", "reason": "upstream"},
    {"status": "skipped", "reason": "disabled"},
])
async def test_provider_decline_never_reports_ok(provider_result):
    connector = SimpleNamespace(create_or_update=Mock())
    async def create_or_update(**kwargs):
        return provider_result
    connector.create_or_update = create_or_update
    result = await gateway(connector).apply_plan(AdsWriteRequest(
        tenant_id="t", platform="yandex_direct",
        plan={"ops": [{"account_id": "a", "object_type": "ad", "payload": {"name": "x"}}]},
    ))
    assert result["status"] == "blocked"
    assert result["results"] == [provider_result]


@pytest.mark.asyncio
async def test_mixed_operations_never_report_whole_plan_success():
    async def create_or_update(**kwargs):
        return {"status": "accepted", "object_id": "provider-id"}
    result = await gateway(SimpleNamespace(create_or_update=create_or_update)).apply_plan(AdsWriteRequest(
        tenant_id="t", platform="yandex_direct",
        plan={"ops": [
            {"account_id": "", "object_type": "ad", "payload": {}},
            {"account_id": "a", "object_type": "ad", "payload": {"name": "x"}},
        ]},
    ))
    assert result["status"] == "blocked"
    assert result["applied"] == 2
