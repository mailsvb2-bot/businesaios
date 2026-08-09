from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from core.offers.catalogs.yaml_catalog import YamlOfferCatalogV1
from entrypoints.api.approval_route_handlers import ApprovalRouteHandlers
from execution.approval_execution_gate import ApprovalExecutionGate
from execution.approval_policy_engine import ApprovalPolicyEngine
from governance.approval_contract import ApprovalDecision, ApprovalOutcome
from governance.approval_store import InMemoryApprovalStore
from governance.approval_workflow import ApprovalWorkflow
from governance.change_control_policy import ChangeControlPolicy
from governance.rbac_contract import RoleId
from runtime.boot.actions_registry import get_spec
from runtime.boot.system_builder_parts.runtime_services import _build_pricing_approval_gate, build_runtime_services
from runtime.handlers.pricing_select import handle_pricing_select
from runtime.pricing import PricingSelectionService


class FakeEffects:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def send_message(self, **kwargs):
        self.calls.append(dict(kwargs))
        return {"ok": True, "evidence": {"source": "connector", "verified": True, "status": "verified", "external_refs": ["message-pricing-1"], "confidence": 1.0}}


class StaticCatalogResolver:
    def __init__(self, catalog) -> None:
        self.catalog = catalog
        self.keys = []

    def resolve(self, *, key):
        self.keys.append(key)
        return self.catalog


class MutableSettingsGateway:
    def __init__(self, value: dict) -> None:
        self.value = dict(value)

    def get_value(self, *, tenant_id: str, key: str):
        assert tenant_id == "tenant-a"
        assert key
        return dict(self.value)


class ExplodingSettingsGateway:
    def get_value(self, **_kwargs):
        raise AssertionError("non-approved delivery must not bind approval preferences")


def _env() -> SimpleNamespace:
    return SimpleNamespace(decision=SimpleNamespace(decision_id="decision-pricing-select", correlation_id="correlation-pricing-select", issuer_id="businesaios-core", action="pricing_select@v1"))


def _approval_gate() -> tuple[ApprovalExecutionGate, ApprovalWorkflow]:
    workflow = ApprovalWorkflow(store=InMemoryApprovalStore())
    gate = ApprovalExecutionGate(approval_policy_engine=ApprovalPolicyEngine(change_control_policy=ChangeControlPolicy()), approval_workflow=workflow)
    return gate, workflow


def _approval_catalog(body: str) -> YamlOfferCatalogV1:
    return YamlOfferCatalogV1.from_spec({"catalog_id": "tenant-a:audit:prod", "offers": [{"offer_id": "audit", "title": "Audit", "base_price_rub": 60_000, "meta": {"commercial": {"position": 0, "requires_human_approval": True}}, "variants": {"a": {"title": "Audit", "body": body}}}]})


@pytest.mark.lock
def test_pricing_select_is_registered_as_confirmed_external_user_effect() -> None:
    spec = get_spec("pricing_select@v1")
    assert spec.execution_category == "external_effect"
    assert spec.external_confirmation_mode == "required"


@pytest.mark.lock
def test_select_tariff_is_registered_as_confirmed_durable_business_write() -> None:
    spec = get_spec("select_tariff@v1")
    assert spec.execution_category == "external_effect"
    assert spec.external_confirmation_mode == "required"


@pytest.mark.lock
def test_boot_builds_the_existing_canonical_pricing_services() -> None:
    source = inspect.getsource(build_runtime_services)
    assert "ctx.set_value('pricing_selection_service', PricingSelectionService()" in source
    assert "ctx.set_value('pricing_approval_execution_gate', _build_pricing_approval_gate()" in source


def test_configured_memory_approval_backend_is_shared_with_control_plane(monkeypatch, tmp_path) -> None:
    poisoned_store = tmp_path / "approvals.json"
    poisoned_store.write_text("{not-json", encoding="utf-8")
    monkeypatch.setenv("BUSINESAIOS_APPROVAL_STORE_BACKEND", "memory")
    monkeypatch.setenv("BUSINESAIOS_APPROVAL_STORE_PATH", str(poisoned_store))
    control_plane = ApprovalRouteHandlers()
    pricing_gate = _build_pricing_approval_gate()
    assert pricing_gate._approval_workflow._store is control_plane.approval_store


def test_real_pricing_selection_uses_catalog_owned_identity_price_and_copy() -> None:
    effects = FakeEffects()
    result = handle_pricing_select({"tenant_id": "business-a", "product_id": "salesbot", "user_id": "user-1", "candidates": [{"offer_id": "sales_entry", "price": 1, "score": 0.9, "message": "UNTRUSTED COPY"}]}, effects, _env(), selection_service=PricingSelectionService())
    assert result["ok"] is True
    assert result["selection"]["offer_id"] == "sales_entry" and result["selection"]["price_rub"] == 600
    assert result["selection_result"]["catalog_id"] == "default:salesbot:prod"
    assert effects.calls[-1]["track_payload"]["price_rub"] == 600 and effects.calls[-1]["text"] != "UNTRUSTED COPY"
    assert effects.calls[-1]["transport_guard"] is None
    assert result["router_evidence"]["source"] == "connector"


def test_non_approved_policy_send_keeps_policy_public_and_has_no_transport_guard() -> None:
    effects = FakeEffects()
    result = handle_pricing_select(
        {"tenant_id": "business-a", "product_id": "salesbot", "user_id": "user-1",
         "channel_policy": {"contact_basis": "existing_customer"},
         "candidates": [{"offer_id": "sales_entry", "score": 0.9}]},
        effects, _env(), selection_service=PricingSelectionService(), settings_gateway=ExplodingSettingsGateway(),
    )
    assert result["ok"] is True
    call = effects.calls[-1]
    assert call["transport_guard"] is None
    assert call["channel_policy"]["contact_basis"] == "existing_customer"
    assert "preference_snapshot" not in call["channel_policy"]


def test_payload_offer_outside_canonical_catalog_is_blocked() -> None:
    effects = FakeEffects()
    result = handle_pricing_select({"tenant_id": "business-a", "product_id": "salesbot", "user_id": "user-1", "candidates": [{"offer_id": "rogue", "price": 1, "score": 1.0, "message": "Rogue"}]}, effects, _env(), selection_service=PricingSelectionService())
    assert result["ok"] is False and result["status"] == "blocked"
    assert effects.calls[-1]["track_event_type"] == "pricing_select_blocked@v1"


def test_unknown_product_cannot_fall_back_to_legacy_catalog() -> None:
    effects = FakeEffects()
    result = handle_pricing_select({"tenant_id": "business-a", "product_id": "typo-product", "user_id": "user-1", "candidates": [{"offer_id": "offer_30", "score": 1.0}]}, effects, _env(), selection_service=PricingSelectionService())
    assert result["ok"] is False and result["status"] == "blocked"


def test_approval_required_offer_binds_recipient_content_delivery_and_preferences_without_policy() -> None:
    original_catalog = _approval_catalog("Approved audit")
    resolver = StaticCatalogResolver(original_catalog)
    gate, workflow = _approval_gate()
    effects = FakeEffects()
    settings = MutableSettingsGateway({"primary": "telegram", "enabled": ["telegram"], "verified": ["telegram"]})
    base_payload = {"tenant_id": "tenant-a", "product_id": "audit", "user_id": "user-1", "channel": "telegram", "candidates": [{"offer_id": "audit", "score": 0.9}]}
    first = handle_pricing_select(base_payload, effects, _env(), selection_service=PricingSelectionService(), catalog_resolver=resolver, approval_gate=gate, settings_gateway=settings)
    assert first["status"] == "approval_required" and first["delivery"] is None and effects.calls == []
    approval_id = first["approval"]["approval_id"]
    workflow.decide(ApprovalDecision(approval_id=approval_id, tenant_id="tenant-a", actor_id="owner-1", role_id=RoleId.OWNER, outcome=ApprovalOutcome.APPROVE, rationale="approved offer"))

    for changed in (
        {**base_payload, "user_id": "user-2", "evidence": {"approval_id": approval_id}},
        {**base_payload, "channel": "email", "evidence": {"approval_id": approval_id}},
        {**base_payload, "channel_policy": {"fallback_channels": ["email"]}, "evidence": {"approval_id": approval_id}},
    ):
        mismatch = handle_pricing_select(changed, effects, _env(), selection_service=PricingSelectionService(), catalog_resolver=resolver, approval_gate=gate, settings_gateway=settings)
        assert mismatch["ok"] is False and mismatch["status"] == "approval_required"
        assert mismatch["approval"]["reason"] == "approval_subject_mismatch"
        assert mismatch["delivery"] is None and effects.calls == []

    resolver.catalog = _approval_catalog("Changed after approval")
    changed_copy = handle_pricing_select({**base_payload, "evidence": {"approval_id": approval_id}}, effects, _env(), selection_service=PricingSelectionService(), catalog_resolver=resolver, approval_gate=gate, settings_gateway=settings)
    assert changed_copy["approval"]["reason"] == "approval_subject_mismatch" and effects.calls == []

    resolver.catalog = original_catalog
    second = handle_pricing_select({**base_payload, "channel_policy": {}, "evidence": {"approval_id": approval_id}}, effects, _env(), selection_service=PricingSelectionService(), catalog_resolver=resolver, approval_gate=gate, settings_gateway=settings)
    assert second["ok"] is True and second["status"] == "verified"
    call = effects.calls[-1]
    assert call["channel"] == "telegram"
    assert call["channel_policy"] is None
    assert callable(call["transport_guard"])
    assert call["transport_guard"](SimpleNamespace()) == ""
    assert call["track_payload"]["price_rub"] == 60_000
    assert "Approved audit" in call["text"]

    settings.value = {"primary": "telegram", "enabled": ["telegram", "email"], "verified": ["telegram", "email"]}
    assert call["transport_guard"](SimpleNamespace()) == "preference_changed"


def test_approval_required_offer_rejects_changed_tenant_preference_before_delivery() -> None:
    resolver = StaticCatalogResolver(_approval_catalog("Approved audit"))
    gate, workflow = _approval_gate()
    effects = FakeEffects()
    settings_gateway = MutableSettingsGateway({"primary": "telegram", "enabled": ["telegram"], "verified": ["telegram"]})
    base_payload = {
        "tenant_id": "tenant-a",
        "product_id": "audit",
        "user_id": "user-1",
        "channel": "telegram",
        "channel_policy": {"contact_basis": "existing_customer"},
        "candidates": [{"offer_id": "audit", "score": 0.9}],
    }
    first = handle_pricing_select(base_payload, effects, _env(), selection_service=PricingSelectionService(),
        catalog_resolver=resolver, approval_gate=gate, settings_gateway=settings_gateway)
    approval_id = first["approval"]["approval_id"]
    workflow.decide(ApprovalDecision(approval_id=approval_id, tenant_id="tenant-a", actor_id="owner-1", role_id=RoleId.OWNER,
        outcome=ApprovalOutcome.APPROVE, rationale="approved preference snapshot"))

    settings_gateway.value = {"primary": "telegram", "enabled": ["telegram", "email"], "verified": ["telegram", "email"]}
    retry = handle_pricing_select({**base_payload, "evidence": {"approval_id": approval_id}}, effects, _env(),
        selection_service=PricingSelectionService(), catalog_resolver=resolver, approval_gate=gate, settings_gateway=settings_gateway)
    assert retry["ok"] is False and retry["status"] == "approval_required"
    assert retry["approval"]["reason"] == "approval_subject_mismatch"
    assert retry["delivery"] is None and effects.calls == []
