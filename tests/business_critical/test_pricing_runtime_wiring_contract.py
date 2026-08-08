from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from execution.approval_execution_gate import ApprovalExecutionGate
from execution.approval_policy_engine import ApprovalPolicyEngine
from governance.approval_contract import ApprovalDecision, ApprovalOutcome
from governance.approval_store import InMemoryApprovalStore
from governance.approval_workflow import ApprovalWorkflow
from governance.change_control_policy import ChangeControlPolicy
from governance.rbac_contract import RoleId
from core.offers.catalogs.yaml_catalog import YamlOfferCatalogV1
from runtime.pricing import PricingSelectionService
from runtime.boot.actions_registry import get_spec
from runtime.boot.system_builder_parts.runtime_services import build_runtime_services
from runtime.handlers.pricing_select import handle_pricing_select


class FakeEffects:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def send_message(self, **kwargs):
        self.calls.append(dict(kwargs))
        return {
            "ok": True,
            "evidence": {
                "source": "connector",
                "verified": True,
                "status": "verified",
                "external_refs": ["message-pricing-1"],
                "confidence": 1.0,
            },
        }


class StaticCatalogResolver:
    def __init__(self, catalog) -> None:
        self.catalog = catalog
        self.keys = []

    def resolve(self, *, key):
        self.keys.append(key)
        return self.catalog


def _env() -> SimpleNamespace:
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-pricing-select",
            correlation_id="correlation-pricing-select",
            issuer_id="businesaios-core",
            action="pricing_select@v1",
        )
    )


def _approval_gate() -> tuple[ApprovalExecutionGate, ApprovalWorkflow]:
    workflow = ApprovalWorkflow(store=InMemoryApprovalStore())
    gate = ApprovalExecutionGate(
        approval_policy_engine=ApprovalPolicyEngine(change_control_policy=ChangeControlPolicy()),
        approval_workflow=workflow,
    )
    return gate, workflow


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
def test_boot_builds_the_existing_canonical_pricing_selection_service() -> None:
    source = inspect.getsource(build_runtime_services)
    assert "from runtime.pricing import PricingSelectionService" in source
    assert "ctx.set_value('pricing_selection_service', PricingSelectionService()" in source


def test_real_pricing_selection_uses_catalog_owned_identity_price_and_copy() -> None:
    effects = FakeEffects()
    result = handle_pricing_select(
        {
            "tenant_id": "business-a",
            "product_id": "salesbot",
            "user_id": "user-1",
            "candidates": [{"offer_id": "sales_entry", "price": 1, "score": 0.9, "message": "UNTRUSTED COPY"}],
        },
        effects,
        _env(),
        selection_service=PricingSelectionService(),
    )

    assert result["ok"] is True
    assert result["selection"]["offer_id"] == "sales_entry"
    assert result["selection"]["price_rub"] == 600
    assert result["selection_result"]["catalog_id"] == "default:salesbot:prod"
    assert result["selection_result"]["tenant_id"] == "business-a"
    assert effects.calls[-1]["tenant_id"] == "business-a"
    assert effects.calls[-1]["user_id"] == "user-1"
    assert effects.calls[-1]["track_payload"]["price_rub"] == 600
    assert effects.calls[-1]["text"] != "UNTRUSTED COPY"
    assert result["router_evidence"]["source"] == "connector"


def test_payload_offer_outside_canonical_catalog_is_blocked() -> None:
    effects = FakeEffects()
    result = handle_pricing_select(
        {
            "tenant_id": "business-a",
            "product_id": "salesbot",
            "user_id": "user-1",
            "candidates": [{"offer_id": "rogue", "price": 1, "score": 1.0, "message": "Rogue"}],
        },
        effects,
        _env(),
        selection_service=PricingSelectionService(),
    )
    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert effects.calls[-1]["track_event_type"] == "pricing_select_blocked@v1"


def test_unknown_product_cannot_fall_back_to_legacy_catalog() -> None:
    effects = FakeEffects()
    result = handle_pricing_select(
        {
            "tenant_id": "business-a",
            "product_id": "typo-product",
            "user_id": "user-1",
            "candidates": [{"offer_id": "offer_30", "score": 1.0}],
        },
        effects,
        _env(),
        selection_service=PricingSelectionService(),
    )
    assert result["ok"] is False and result["status"] == "blocked"
    assert effects.calls[-1]["track_event_type"] == "pricing_select_blocked@v1"


def test_approval_required_offer_uses_canonical_gate_before_delivery() -> None:
    catalog = YamlOfferCatalogV1.from_spec({
        "catalog_id": "tenant-a:audit:prod",
        "offers": [{
            "offer_id": "audit",
            "title": "Audit",
            "base_price_rub": 60_000,
            "meta": {"commercial": {"position": 0, "requires_human_approval": True}},
            "variants": {"a": {"title": "Audit", "body": "Approved audit"}},
        }],
    })
    gate, workflow = _approval_gate()
    effects = FakeEffects()
    base_payload = {
        "tenant_id": "tenant-a",
        "product_id": "audit",
        "user_id": "user-1",
        "candidates": [{"offer_id": "audit", "score": 0.9}],
    }
    first = handle_pricing_select(base_payload, effects, _env(), selection_service=PricingSelectionService(),
        catalog_resolver=StaticCatalogResolver(catalog), approval_gate=gate)
    assert first["status"] == "approval_required"
    assert first["delivery"] is None and effects.calls == []
    approval_id = first["approval"]["approval_id"]
    approved = workflow.decide(ApprovalDecision(
        approval_id=approval_id, tenant_id="tenant-a", actor_id="owner-1", role_id=RoleId.OWNER,
        outcome=ApprovalOutcome.APPROVE, rationale="approved offer",
    ))
    assert approved.status.value == "approved"

    second_payload = {**base_payload, "evidence": {"approval_id": approval_id}}
    second = handle_pricing_select(second_payload, effects, _env(), selection_service=PricingSelectionService(),
        catalog_resolver=StaticCatalogResolver(catalog), approval_gate=gate)
    assert second["ok"] is True and second["status"] == "verified"
    assert effects.calls[-1]["track_payload"]["offer_id"] == "audit"
    assert effects.calls[-1]["track_payload"]["price_rub"] == 60_000
