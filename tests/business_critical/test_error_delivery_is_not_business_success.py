from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.pricing.rl.selection_service import PricingSelectionService
from runtime.governance import PolicyUpdateGateError
from runtime.handler_impl.domains.admin_ops import handle_admin_user_card
from runtime.handlers import ads_rl_suggest as ads_rl_suggest_module
from runtime.handlers.ai_ceo_plan import handle_ai_ceo_plan
from runtime.handlers.pricing_select import handle_pricing_select


class FakeEffects:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.events: list[dict] = []

    def send_message(self, **kwargs):
        self.calls.append(dict(kwargs))
        return {
            "ok": True,
            "evidence": {
                "source": "connector",
                "verified": True,
                "status": "verified",
                "external_refs": [f"message-{len(self.calls)}"],
                "confidence": 1.0,
            },
        }

    def track_event(self, **kwargs):
        self.events.append(dict(kwargs))
        return {"ok": True}


def _env(action: str) -> SimpleNamespace:
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id=f"decision-{action}",
            correlation_id=f"correlation-{action}",
            issuer_id="businesaios-core",
            action=action,
            tenant_id="business-a",
        )
    )


@pytest.mark.lock
def test_pricing_no_candidate_is_not_success_even_when_error_message_is_delivered() -> None:
    effects = FakeEffects()

    result = handle_pricing_select(
        {
            "tenant_id": "business-a",
            "product_id": "crm-pro",
            "user_id": "owner-1",
            "candidates": [],
        },
        effects,
        _env("pricing_select@v1"),
        selection_service=PricingSelectionService(),
    )

    assert effects.calls[-1]["track_event_type"] == "pricing_select_blocked@v1"
    assert result["delivery"]["ok"] is True
    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert result["router_evidence"] is None


@pytest.mark.lock
def test_ai_ceo_planner_error_is_not_success_even_when_error_message_is_delivered() -> None:
    class BrokenPlanner:
        def build_plan(self, **_kwargs):
            raise ValueError("planner unavailable")

    effects = FakeEffects()
    result = handle_ai_ceo_plan(
        {
            "tenant_id": "business-a",
            "user_id": "owner-1",
            "objective": "grow profit",
        },
        effects,
        _env("ai_ceo_plan@v1"),
        planner=BrokenPlanner(),
    )

    assert effects.calls[-1]["track_event_type"] == "ai_ceo_plan_error@v1"
    assert result["delivery"]["ok"] is True
    assert result["ok"] is False
    assert result["status"] == "failed"
    assert result["router_evidence"] is None


@pytest.mark.lock
def test_admin_card_read_failure_is_not_success_even_when_error_message_is_delivered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_read_model(**_kwargs):
        raise RuntimeError("event store unavailable")

    monkeypatch.setattr("core.payments.read_model.latest_payment_status", fail_read_model)
    effects = FakeEffects()

    result = handle_admin_user_card(
        {
            "tenant_id": "business-a",
            "product_id": "crm-pro",
            "admin_id": "admin-1",
            "target_user_id": "user-7",
        },
        effects,
        _env("admin_user_card@v1"),
        event_store=object(),
    )

    assert effects.calls[-1]["track_event_type"] == "admin_user_card_failed@v1"
    assert result["delivery"]["ok"] is True
    assert result["ok"] is False
    assert result["status"] == "failed"
    assert result["router_evidence"] is None


@pytest.mark.lock
def test_ads_rl_cooldown_is_not_success_even_when_block_message_is_delivered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BlockedGate:
        def bind_event_store(self, _event_store) -> None:
            return None

        def propose(self, **_kwargs) -> None:
            raise PolicyUpdateGateError("cooldown")

    monkeypatch.setattr(ads_rl_suggest_module, "bind_runtime_state", lambda **_kwargs: None)
    monkeypatch.setattr(ads_rl_suggest_module, "_SUGGEST_GATE", BlockedGate())
    effects = FakeEffects()

    result = ads_rl_suggest_module.handle_ads_rl_suggest(
        {
            "tenant_id": "business-a",
            "user_id": "owner-1",
        },
        effects,
        _env("ads_rl_suggest@v1"),
        event_store=object(),
    )

    assert effects.calls[-1]["track_event_type"] == "ads_rl_suggest_blocked@v1"
    assert result["delivery"]["ok"] is True
    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert result["router_evidence"] is None
