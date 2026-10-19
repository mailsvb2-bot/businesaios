from types import SimpleNamespace

import pytest

import governance.economic_layer as economics


class _Survival:
    def evaluate(self):
        return SimpleNamespace(allow_execution=True, reason="ok")


class _Policy:
    def __init__(self):
        self.called = 0

    def review(self, decision, world_state):
        self.called += 1
        return SimpleNamespace(allowed=True, operator_required=False, reason="ok", metadata={})


def _envelope(action, payload=None, cost=0.0):
    return SimpleNamespace(decision=SimpleNamespace(action=action, payload=payload or {}, cost=cost))


@pytest.fixture
def layer(monkeypatch):
    monkeypatch.setattr(economics, "is_strict_mode", lambda: True)
    policy = _Policy()
    layer = economics.EconomicAutonomyLayer(survival=_Survival())
    layer._economic_policy_engine = policy
    return layer, policy


def test_start_menu_message_needs_no_fictional_capital(layer):
    evaluator, policy = layer
    result = evaluator.review(
        decision_env=_envelope("send_message@v1", {"user_id": "u", "text": "ClientPlatform menu"}),
        world_state={"economy": {}},
    )
    assert result.allow is True
    assert policy.called == 1


@pytest.mark.parametrize("action,payload,cost", [
    ("purchase@v1", {"text": "buy"}, 0.0),
    ("transfer@v1", {}, 0.0),
    ("send_message@v1", {"amount": 12}, 0.0),
    ("send_message@v1", {"economy": {"requested_budget": 100}}, 0.0),
    ("send_message@v1", {"text": "hi"}, 5.0),
])
def test_strict_economic_guards_remain_for_financial_requests(layer, action, payload, cost):
    evaluator, policy = layer
    result = evaluator.review(
        decision_env=_envelope(action, payload, cost),
        world_state={"economy": {}},
    )
    assert result.allow is False
    assert result.reason == "missing_capital_state"
    assert policy.called == 0


def test_survival_veto_remains_for_message(layer):
    evaluator, policy = layer
    evaluator.survival = SimpleNamespace(evaluate=lambda: SimpleNamespace(allow_execution=False, reason="offline"))
    result = evaluator.review(
        decision_env=_envelope("send_message@v1", {"text": "menu"}),
        world_state={},
    )
    assert not result.allow
    assert result.reason.startswith("survival_block:")
    assert policy.called == 0
