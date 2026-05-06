from __future__ import annotations

import pytest

from core.api.versioning import ApiVersion, parse_api_version
from core.security.auth import AuthContext, AuthForbidden, require_scope
from core.tenancy.request_context import get_tenant_id, tenant_scope
from infra.audit_event import AuditEvent
from infra.audit_sink import InMemoryAuditSink
from interfaces.ads.base import AdsConnectorError, AdsPlatform
from interfaces.ads.connector_shared import (
    http_get_compat,
    pending_account_id_from_raw,
    resolve_secret_required,
)
from observability.execution_metrics import ExecutionMetrics
from runtime.decision_gateway import DecisionGateway, DecisionGatewayContractError, RuntimeDecisionGateway


class _DecisionInputService:
    def read_packet(self, packet):
        return {"packet": packet}


class _EnrichmentService:
    def __init__(self, payload):
        self.payload = payload

    def build(self, contract):
        return self.payload


class _Observability:
    def __init__(self):
        self.calls = []

    def record_model_snapshot(self, **kwargs):
        self.calls.append(kwargs)


class _HttpBad:
    async def get(self, *args, **kwargs):
        return ["not", "a", "mapping"]


class _IssuerMissing:
    pass


def test_decision_gateway_fails_closed_on_bad_enrichment() -> None:
    gateway = DecisionGateway(
        decision_input_service=_DecisionInputService(),
        enrichment_service=_EnrichmentService([("x", 1)]),
        observability=_Observability(),
    )
    with pytest.raises(DecisionGatewayContractError):
        gateway.route(packet={"id": 1}, canonical_context={}, decision_core_callable=lambda s: s)


@pytest.mark.asyncio
async def test_http_get_compat_requires_mapping_payload() -> None:
    with pytest.raises(AdsConnectorError):
        await http_get_compat(_HttpBad(), platform=AdsPlatform.GOOGLE_ADS, url="https://x", headers={})


def test_pending_account_id_digest_is_stable_for_reordered_payload() -> None:
    left = pending_account_id_from_raw(
        tenant_id="t1",
        raw={"b": 2, "a": {"x": [3, 2, 1]}},
        candidate_keys=("id",),
        pending_prefix="pending",
    )
    right = pending_account_id_from_raw(
        tenant_id="t1",
        raw={"a": {"x": [3, 2, 1]}, "b": 2},
        candidate_keys=("id",),
        pending_prefix="pending",
    )
    assert left == right


def test_require_scope_rejects_missing_scope() -> None:
    ctx = AuthContext(tenant_id="t1", subject="u1", scopes=("read",))
    with pytest.raises(AuthForbidden):
        require_scope(ctx, "write")


def test_tenant_scope_resets_context() -> None:
    before = get_tenant_id()
    with tenant_scope("tenant-42") as tenant_id:
        assert tenant_id == "tenant-42"
        assert get_tenant_id() == "tenant-42"
    assert get_tenant_id() == before


def test_api_version_helpers_cover_major_match_and_parse() -> None:
    assert parse_api_version("v2.7").matches_major(ApiVersion(2, 0)) is True


def test_audit_sink_supports_snapshot_and_append_many() -> None:
    sink = InMemoryAuditSink()
    events = [
        AuditEvent(event_name="a", actor="system", category="test", payload={}),
        AuditEvent(event_name="b", actor="system", category="test", payload={}),
    ]
    sink.append_many(events)
    assert sink.snapshot() == tuple(events)


def test_execution_metrics_expose_counter_snapshot() -> None:
    metrics = ExecutionMetrics()
    metrics.record_execution(route="decision", status="ok", duration_ms=12)
    snap = metrics.snapshot()
    assert snap["execution.route.decision"] == 1.0
    assert snap["execution.status.ok"] == 1.0


def test_runtime_decision_gateway_requires_issue_surface() -> None:
    with pytest.raises(DecisionGatewayContractError):
        RuntimeDecisionGateway(issuer=_IssuerMissing()).issue(state={})


def test_resolve_secret_required_ignores_blank_cfg_value() -> None:
    class _Vault:
        def get_secret(self, *args):
            return "secret"

    assert resolve_secret_required(cfg_value="   ", vault=_Vault(), vault_key="X", error_message="boom") == "secret"
