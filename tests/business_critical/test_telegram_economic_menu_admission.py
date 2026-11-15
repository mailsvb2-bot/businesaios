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
    result = evaluator.review(decision_env=_envelope("send_message@v1", {"user_id": "u", "text": "ClientPlatform menu"}), world_state={"economy": {}})
    assert result.allow is True
    assert policy.called == 1

@pytest.mark.parametrize("action,payload,cost", [
    ("purchase@v1", {"text": "buy"}, 0.0),
    ("transfer@v1", {}, 0.0),
    ("send_message@v1", {"amount": 12}, 0.0),
    ("send_message@v1", {"economy": {"requested_budget": 100}}, 0.0),
    ("send_message@v1", {"text": "hi"}, 5.0),
    ("send_message@v1", {"text": "hi"}, float("nan")),
    ("send_message@v1", {"text": "hi"}, float("inf")),
    ("send_message@v1", {"text": "hi"}, "not-a-number"),
    ("send_message@v1", {"text": "hi"}, None),
    ("send_message@v1", {"text": "hi"}, False),
    ("send_message@v1", {"user_id": "u", "amount": 12, "text": "hi"}, 0.0),
    ("send_message@v1", {"user_id": "u", "economy": {"requested_budget": 12}, "text": "hi"}, 0.0),
    ("send_message@v1", {"user_id": "u", "text": "hi", "unexpected": True}, 0.0),
    ("send_message@v1", {"user_id": "u"}, 0.0),
    ("send_message@v1", {"text": "hi"}, 0.0),
])
def test_strict_economic_guards_remain_for_financial_requests(layer, action, payload, cost):
    evaluator, policy = layer
    result = evaluator.review(decision_env=_envelope(action, payload, cost), world_state={"economy": {}})
    assert result.allow is False
    assert result.reason == "missing_capital_state"
    assert policy.called == 0

def test_survival_veto_remains_for_message(layer):
    evaluator, policy = layer
    evaluator.survival = SimpleNamespace(evaluate=lambda: SimpleNamespace(allow_execution=False, reason="offline"))
    result = evaluator.review(decision_env=_envelope("send_message@v1", {"text": "menu"}), world_state={})
    assert not result.allow
    assert result.reason.startswith("survival_block:")
    assert policy.called == 0

def test_real_economic_policy_is_still_invoked_for_menu(monkeypatch):
    monkeypatch.setattr(economics, "is_strict_mode", lambda: True)
    evaluator = economics.EconomicAutonomyLayer(survival=_Survival())
    result = evaluator.review(decision_env=_envelope("send_message@v1", {"user_id": "u", "text": "Welcome"}), world_state={"economy": {}})
    assert result.allow is True, result.reason
    assert result.economic is not None

@pytest.mark.parametrize("extra,allowed", [
    ({"tenant_id": "tenant-live", "product_id": "organization_platform", "domain": "organization_platform", "product_version": "v1", "actor_id": "10001", "idempotency_key": "decision:abc123", "world_model_meta": {}}, True),
    ({"amount": 200}, False),
    ({"expected_cost": 20}, False),
    ({"idempotency_key": "random"}, False),
    ({"world_model_meta": 7}, False),
    ({"meta": {"world_model_meta": {"semantic_state_id": "s"}}}, True),
    ({"meta": {"requested_budget": 100}}, False),
    ({"meta": {"world_model_meta": 0}}, False),
])
def test_canonical_decision_without_cost_can_open_menu(layer, extra, allowed):
    from contracts.decisioning.sovereign_decision_contract import Decision, DecisionEnvelope
    decision = Decision(decision_id="d", issuer_id="issuer", issued_at_ms=1, expires_at_ms=2,
                        policy_id="telegram", action="send_message@v1", payload={"user_id": "u", "text": "ClientPlatform menu", **extra},
                        snapshot_id="s", state_hash="h", correlation_id="c", state_schema_version=1, action_schema_version=1)
    envelope = DecisionEnvelope(decision=decision, payload_hash="h", signature="test-only", kid="test-only")
    evaluator, policy = layer
    result = evaluator.review(decision_env=envelope, world_state={})
    assert result.allow is allowed, result.reason
    # Fully bound single-recipient text is never sent through a spend policy.
    # Legacy unbound / ambiguous envelopes retain their previous review.
    assert policy.called == int(allowed and not (extra.get("tenant_id") == "tenant-live"))

@pytest.mark.parametrize("tenant_id,allowed", [("tenant-live", True), ("", False), (" ", False), (7, False), (None, True)])
def test_tenant_scoped_free_menu_admission(layer, tenant_id, allowed):
    evaluator, policy = layer
    payload = {"tenant_id": tenant_id, "user_id": "u", "text": "Menu"}
    result = evaluator.review(decision_env=_envelope("send_message@v1", payload), world_state={})
    assert result.allow is allowed, result.reason
    assert policy.called == int(allowed and tenant_id is None)
    if not allowed:
        assert result.reason == "missing_capital_state"



@pytest.mark.parametrize("action,op,arg", [
    ("business_ops_summary@v1", "cockpit", "cpm:growth-an:7"),
    ("business_ops_summary@v1", "cockpit", "cpm:money"),
    ("business_ops_summary@v1", "cockpit", "cpm:growth"),
    ("business_ops_summary@v1", "cockpit", "cpm:customers:42"),
    ("business_ops_summary@v1", "cockpit", "cpm:payments:1"),
    ("business_ops_summary@v1", "cockpit", "cpm:team:0"),
    ("business_ops_summary@v1", "cockpit", "cpm:calendar"),
    ("sales_pipeline@v1", "list", ""),
    ("bookings@v1", "ad_channels", ""),
])
def test_canonical_read_projection_needs_no_fictional_capital(layer, action, op, arg):
    evaluator, policy = layer
    payload = {"tenant_id": "tenant-live", "user_id": "owner", "actor_id": "owner",
               "op": op, "arg": arg, "meta": {"world_model_meta": {}},
               "goal_id": "owner-goal", "autonomy_tier": "supervised"}
    verdict = evaluator.review(decision_env=_envelope(action, payload, 0.0), world_state={})
    assert verdict.allow is True
    assert verdict.metadata["budget_class"] == "read_projection"
    assert policy.called == 0


@pytest.mark.parametrize("action,op,arg,extra,cost", [
    ("business_ops_summary@v1", "cockpit", "cpm:money", {"amount": 10}, 0.0),
    ("business_ops_summary@v1", "cockpit", "cpm:money", {"estimated_cost": 10}, 0.0),
    ("business_ops_summary@v1", "cockpit", "cpm:money", {"meta": {"requested_budget": 10}}, 0.0),
    ("business_ops_summary@v1", "cockpit", "cpm:money", {"user_id": ""}, 0.0),
    ("business_ops_summary@v1", "cockpit", "cpm:money", {"tenant_id": " "}, 0.0),
    ("business_ops_summary@v1", "cockpit", "cpm:pay-rf:ref", {}, 0.0),
    ("business_ops_summary@v1", "cockpit", "cpm:payments:charge", {}, 0.0),
    ("business_ops_summary@v1", "cockpit", "cpm:team:0:write", {}, 0.0),
    ("business_ops_summary@v1", "cockpit", "cpm:money", {}, 1.0),
    ("business_ops_summary@v1", "cockpit", "cpm:money", {}, float("nan")),
    ("sales_pipeline@v1", "add", "", {}, 0.0),
    ("bookings@v1", "dispatch", "", {}, 0.0),
])
def test_strict_economics_still_vetoes_unsafe_menu_actions(layer, action, op, arg, extra, cost):
    evaluator, policy = layer
    payload = {"tenant_id": "tenant-live", "user_id": "owner", "op": op, "arg": arg, **extra}
    verdict = evaluator.review(decision_env=_envelope(action, payload, cost), world_state={})
    assert verdict.allow is False
    assert verdict.reason == "missing_capital_state"
    assert policy.called == 0


def test_canonical_read_projection_does_not_override_survival_or_degraded_world(layer):
    evaluator, policy = layer
    payload = {"tenant_id": "tenant-live", "user_id": "owner",
               "op": "cockpit", "arg": "cpm:money"}
    evaluator.survival = SimpleNamespace(evaluate=lambda: SimpleNamespace(allow_execution=False, reason="offline"))
    assert evaluator.review(decision_env=_envelope("business_ops_summary@v1", payload),
                            world_state={}).reason.startswith("survival_block:")
    evaluator.survival = _Survival()
    assert evaluator.review(decision_env=_envelope("business_ops_summary@v1", payload),
                            world_state={"mode": "degraded", "reason": "missing_snapshot"}).reason.startswith("degraded_world:")
    assert policy.called == 0
