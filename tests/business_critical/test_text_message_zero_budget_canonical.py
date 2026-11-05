"""Text delivery is quota-free, without bypassing decision or provider security."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from contracts.action_impact_contract import ActionExecutionContext
from core.safety.controls.action_budget.guard import ActionBudgetGuard
from core.safety.controls.action_budget.ledger import InMemoryActionBudgetLedger
from core.safety.controls.action_budget.models import ActionBudget, is_budget_free_text_message
from core.safety.controls.action_context import SafetyActionContext
from core.safety.controls.control_result import ControlStatus
from core.safety.operational.action_classifier import ActionClassifier
from core.safety.operational.action_cost_model import ActionCostModel
from core.safety.operational.action_impact_builder import ActionImpactBuilder
from core.safety.operational.action_registry import build_default_operational_action_registry
from core.safety.operational.operational_budget_accountant import OperationalBudgetAccountant
from governance.economic_layer import EconomicAutonomyLayer


class _Survival:
    def evaluate(self):
        return SimpleNamespace(allow_execution=True, reason="ok")


@pytest.fixture
def strict_layer(monkeypatch):
    import governance.economic_layer as economics
    monkeypatch.setattr(economics, "is_strict_mode", lambda: True)
    return EconomicAutonomyLayer(survival=_Survival())


def _text(channel="telegram"):
    return {
        "tenant_id": "tenant-live",
        "user_id": "user-1",
        "text": "Добро пожаловать в КлиентПлатформ",
        "channel": channel,
        "chat_id": "111",
        "reply_markup": {"inline_keyboard": []},
        "actor_id": "user-1",
        "meta": {"world_model_meta": {}, "inbound_user_reply": {
            "tenant_id": "tenant-live", "channel": channel,
        }},
        "idempotency_key": "decision:abc",
    }


@pytest.mark.parametrize("channel", ["telegram", "vk", "max", "whatsapp"])
def test_plain_text_bypasses_only_budgets_across_canonical_layers(strict_layer, channel):
    payload = _text(channel)
    assert is_budget_free_text_message("send_message@v1", payload)

    decision = SimpleNamespace(action="send_message@v1", payload=payload, cost=0)
    result = strict_layer.review(decision_env=SimpleNamespace(decision=decision), world_state={})
    assert result.allow is True, result.reason

    ledger = InMemoryActionBudgetLedger()
    ledger.record("tenant-live", estimated_cost=5)
    guard = ActionBudgetGuard(ledger, ActionBudget(max_cost=0, max_actions=0))
    assert guard.evaluate(SafetyActionContext(
        action="send_message@v1", tenant_id="tenant-live",
        user_id="user-1", payload=payload,
    )).status == ControlStatus.ALLOW

    ctx = ActionExecutionContext(
        tenant_id="tenant-live", user_id="user-1",
        action_name="send_message@v1", payload=payload,
        execution_id="decision-1",
    )
    builder = ActionImpactBuilder(
        ActionClassifier(build_default_operational_action_registry()),
        ActionCostModel(),
    )
    accounting = OperationalBudgetAccountant().to_envelope(ctx, builder.build(ctx))
    assert (accounting.actions_count, accounting.outbound_count, accounting.budget_minor) == (0, 0, 0)
    assert ledger.snapshot("tenant-live") == (5.0, 1)


@pytest.mark.parametrize("override", [
    {"campaign_id": "campaign-1"},
    {"kind": "broadcast"},
    {"recipients": ["u1", "u2"]},
    {"recipient_count": 2},
    {"estimated_cost": 100},
    {"economy": {"requested_budget": 50}},
    {"payment_id": "invoice"},
    {"amount": 3},
    {"meta": {"requested_budget": 30}},
    {"unexpected": "paid"},
])
def test_unsafe_or_paid_text_never_gets_free_budget_class(strict_layer, override):
    payload = {**_text(), **override}
    assert not is_budget_free_text_message("send_message@v1", payload)
    decision = SimpleNamespace(action="send_message@v1", payload=payload, cost=0)
    verdict = strict_layer.review(decision_env=SimpleNamespace(decision=decision), world_state={})
    assert verdict.allow is False
    assert verdict.reason == "missing_capital_state"


@pytest.mark.parametrize("cost", [1.0, -1.0, True, float("inf"), float("nan")])
def test_explicit_legacy_cost_cannot_hide_inside_free_text(strict_layer, cost):
    decision = SimpleNamespace(action="send_message@v1", payload=_text(), cost=cost)
    result = strict_layer.review(decision_env=SimpleNamespace(decision=decision), world_state={})
    assert not result.allow and result.reason == "missing_capital_state"


def test_non_text_and_other_tenant_still_subject_to_action_budget():
    payload = _text()
    ledger = InMemoryActionBudgetLedger()
    ledger.record("tenant-live", estimated_cost=2)
    guard = ActionBudgetGuard(ledger, ActionBudget(max_cost=1, max_actions=0))
    for action, tenant in (("capture_payment", "tenant-live"), ("send_message@v1", "another-tenant")):
        verdict = guard.evaluate(SafetyActionContext(
            action=action, tenant_id=tenant, user_id="user-1", payload=payload,
        ))
        assert verdict.status == ControlStatus.BLOCK


def test_zero_cost_text_cannot_be_blocked_by_financial_stoploss(strict_layer):
    payload = _text()
    decision = SimpleNamespace(action="send_message@v1", payload=payload, cost=0)
    for economic_state in (
        {"open_stop_loss_flags": ["active_stop"]},
        {"protected_cash_reserve": 10000, "cash_on_hand": 0},
    ):
        verdict = strict_layer.review(
            decision_env=SimpleNamespace(decision=decision),
            world_state={"economics_state": economic_state},
        )
        assert verdict.allow, verdict.reason
        assert verdict.metadata["budget_class"] == "text_delivery"


def test_text_still_obeys_non_budget_survival_veto(strict_layer):
    strict_layer.survival = SimpleNamespace(
        evaluate=lambda: SimpleNamespace(allow_execution=False, reason="stopped")
    )
    verdict = strict_layer.review(
        decision_env=SimpleNamespace(
            decision=SimpleNamespace(action="send_message@v1", payload=_text(), cost=0)
        ),
        world_state={},
    )
    assert not verdict.allow and verdict.reason.startswith("survival_block:")
