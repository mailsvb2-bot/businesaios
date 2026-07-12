from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from core.pricing.rl.selection_service import PricingSelectionService
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


def _env() -> SimpleNamespace:
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-pricing-select",
            correlation_id="correlation-pricing-select",
        )
    )


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

    assert "PricingSelectionService" in source
    assert "ctx.set_value('pricing_selection_service', PricingSelectionService()" in source


def test_real_pricing_selection_service_drives_tenant_aware_delivery() -> None:
    effects = FakeEffects()

    result = handle_pricing_select(
        {
            "tenant_id": "business-a",
            "product_id": "crm-pro",
            "user_id": "user-1",
            "candidates": [
                {"offer_id": "basic", "price": 100, "score": 0.2, "message": "Basic"},
                {"offer_id": "pro", "price": 900, "score": 0.9, "message": "CRM Pro"},
            ],
        },
        effects,
        _env(),
        selection_service=PricingSelectionService(),
    )

    assert result["ok"] is True
    assert result["selection"]["offer_id"] == "pro"
    assert effects.calls[-1]["tenant_id"] == "business-a"
    assert effects.calls[-1]["user_id"] == "user-1"
    assert effects.calls[-1]["text"] == "CRM Pro"
    assert result["router_evidence"]["source"] == "connector"
