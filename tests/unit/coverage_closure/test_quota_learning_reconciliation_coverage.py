from __future__ import annotations

from types import SimpleNamespace

import pytest

from billing.quota_policy import EffectiveQuotaPolicy, QuotaPolicyResolver
from core.autopilot.guardrails import enforce_change_rate, evaluate_stop_loss, evaluate_stop_loss_window
from core.learning import learning_system as learning_module
from core.learning.learning_system import BanditStats, LearningSystem
from runtime.economic_core.cross_domain_reconciliation import build_cross_domain_reconciliation_snapshot
from tenancy.tenant_billing_scope import BillingMode


def test_quota_guardrails_learning_and_reconciliation(monkeypatch: pytest.MonkeyPatch) -> None:
    policy = EffectiveQuotaPolicy(
        tenant_id="tenant-1",
        plan_id=None,
        quota_limits={"events": 10},
        hard_stop_dimensions=frozenset({"events"}),
        allow_overage=True,
    )
    policy.validate()
    assert policy.limit_for("events") == 10.0
    assert policy.limit_for("missing") is None
    assert policy.hard_stop_for("events")
    assert not policy.hard_stop_for("soft")
    with pytest.raises(ValueError):
        policy.limit_for("")
    with pytest.raises(ValueError):
        policy.hard_stop_for("")
    with pytest.raises(ValueError):
        EffectiveQuotaPolicy("tenant-1", None, {"": 1}).validate()
    with pytest.raises(ValueError):
        EffectiveQuotaPolicy("tenant-1", None, {"x": -1}).validate()

    class Limit:
        def __init__(self, dimension: str, limit: float, hard_stop: bool):
            self.dimension, self.limit, self.hard_stop = dimension, limit, hard_stop

        def normalized_copy(self):
            return self

    plan = SimpleNamespace(plan_id=SimpleNamespace(value="pro"), quota_limits=(Limit("events", 100, True), Limit("jobs", 50, False)))
    binding = SimpleNamespace(
        plan_id=SimpleNamespace(value="pro"),
        overrides={
            "quota_limits": {"events": 80, "api": 20},
            "hard_stop_dimensions": ["api"],
            "billing_mode": "prepaid",
            "invoice_enabled": False,
            "allow_overage": True,
            "metadata": {"source": "binding"},
        },
    )
    bundle = SimpleNamespace(
        quotas={"events": 70, "jobs": 60},
        billing_scope=SimpleNamespace(mode=BillingMode.POSTPAID, invoice_enabled=True, allow_overage=False),
    )
    plan_store = SimpleNamespace(get_binding=lambda _tid: binding, get_plan=lambda _tid: plan)
    bundle_store = SimpleNamespace(get=lambda _tid: bundle)
    resolved = QuotaPolicyResolver(tenant_plan_store=plan_store, tenant_policy_store=bundle_store).resolve(tenant_id="tenant-1")
    assert resolved.quota_limits == {"events": 70.0, "jobs": 50.0, "api": 20.0}
    assert resolved.hard_stop_dimensions == frozenset({"api"})
    assert resolved.billing_mode is BillingMode.PREPAID
    assert resolved.metadata["source"] == "binding"
    default = QuotaPolicyResolver().resolve(tenant_id="tenant-2")
    assert default.quota_limits == {} and default.invoice_enabled

    safety = SimpleNamespace(
        stop_loss_cac_days=2,
        stop_loss_max_cac_minor=100,
        stop_loss_profit_days=2,
        stop_loss_min_profit_minor=-50,
        stop_loss_max_spend_minor_no_conv=200,
        stop_loss_no_conv_days=2,
    )
    contract = SimpleNamespace(safety_policy=safety, constraints=SimpleNamespace(max_price_changes_per_day=3))
    assert evaluate_stop_loss_window(contract=contract, window=[]).allow
    assert evaluate_stop_loss_window(contract=contract, window=[{"cac_minor": 101}]).reason == "STOP_LOSS_CAC"
    assert evaluate_stop_loss_window(contract=contract, window=[{"profit_minor": -60}, {"profit_minor": -70}]).reason == "STOP_LOSS_PROFIT"
    assert evaluate_stop_loss_window(contract=contract, window=[{"spend_minor": 100}, {"spend_minor": 100, "conversions": 0}]).reason == "STOP_LOSS_NO_CONV"
    assert evaluate_stop_loss_window(contract=contract, window=[{"spend_minor": 500, "conversions": 1}]).allow
    assert evaluate_stop_loss(contract=contract, metrics={"profit_minor_today": "0", "cac_minor_today": "0"}).allow
    assert not enforce_change_rate(contract=contract, changes_today=3).allow
    assert enforce_change_rate(contract=contract, changes_today=2).allow

    assert BanditStats().mean == 0 and BanditStats().ltv_mean == 0
    learning = LearningSystem(min_samples=2, collapse_threshold=-5, ltv_collapse_threshold=-5)
    replay = learning.offline_replay(
        [
            {"type": "reward_observed", "decision_id": "missing", "reward": 9},
            {"type": "decision_issued", "decision_id": "d1", "policy_id": "p1"},
            {"type": "reward_observed", "decision_id": "d1", "reward": 3},
            {"type": "reward_observed", "decision_id": "d1", "reward": None},
        ]
    )
    assert replay["p1"].n == 2 and replay["p1"].reward_sum == 3
    assert learning.pick_best_policy() is None
    learning.observe_reward(policy_id="good", reward=3, ltv=4)
    learning.observe_reward(policy_id="good", reward=5, ltv=6)
    assert learning.pick_best_policy() == "good"
    assert learning.maybe_propose_deployment()["candidate_policy_id"] == "good"
    assert learning.maybe_propose_deployment() is None

    collapse = LearningSystem(min_samples=1, collapse_threshold=0, ltv_collapse_threshold=-100)
    collapse.observe_reward(policy_id="bad", reward=-1, ltv=1)
    assert collapse.maybe_propose_deployment() == {"kind": "rollback", "reason": "reward_collapse"}
    assert collapse.maybe_propose_deployment() is None

    ltv = LearningSystem(min_samples=1, collapse_threshold=-100, ltv_collapse_threshold=0)
    ltv.observe_reward(policy_id="bad", reward=1, ltv=-1)
    assert ltv.maybe_propose_deployment()["reason"] == "ltv_collapse"

    drop = LearningSystem(min_samples=1, collapse_threshold=-100, ltv_collapse_threshold=-100, ltv_drop_pct=0.2)
    drop._last_ltv_mean["p"] = 10
    drop.observe_reward(policy_id="p", reward=1, ltv=5)
    assert drop.maybe_propose_deployment()["reason"] == "ltv_drop"

    class Registry:
        def latest_validated(self):
            return SimpleNamespace(candidate_policy_id="offline")

    offline = LearningSystem(min_samples=99, model_registry=Registry())
    assert offline.maybe_propose_deployment()["candidate_policy_id"] == "offline"
    assert offline.maybe_propose_deployment() is None
    with pytest.raises(RuntimeError, match="MODEL_REGISTRY_CONTRACT_VIOLATION"):
        LearningSystem(model_registry=object()).maybe_propose_deployment()

    monkeypatch.setattr(learning_module, "current_tenant_id", lambda: "tenant-1")
    monkeypatch.setattr(learning_module.time, "time", lambda: 123.0)
    world = learning.build_deploy_world_state({"kind": "deploy"})
    assert world.tenant_id == "tenant-1" and world.deployment_proposal == {"kind": "deploy"}

    inconsistent = build_cross_domain_reconciliation_snapshot(
        client_outcome_truth={"revenue_corrected_minor": "bad", "source_channel": "ads"},
        billing_truth={"corrected_amount_minor": 1000, "billing_status": "missing"},
        click_truth={"billable_candidate": True, "click_billable_fact_ready": False},
        spend_truth={"spend_total_minor": 0},
        spend_source={"status": "ready"},
        click_collection={"collection_preview": True, "execution_result": True},
        click_provider_dispatch={"provider_dispatch": False},
        spend_runtime_request={},
        click_sealed_execution={},
        spend_sealed_execution={},
    )
    assert not inconsistent["consistent"]
    assert {"click_candidate_without_billable_fact", "spend_source_ready_without_spend_fact", "revenue_without_billing_status", "paid_channel_without_tracking_token"} <= set(inconsistent["issues"])

    consistent = build_cross_domain_reconciliation_snapshot(
        client_outcome_truth={"corrected_revenue": 20.0, "source_channel": "organic"},
        billing_truth={"billing_status": "booked"},
        click_truth={"billable_candidate": False, "click_billable_fact_ready": True},
        spend_truth={"spend_total_minor": 500},
        spend_source={"status": "ready", "tracking_token": "t"},
        click_collection={"settlement_result": True},
        click_provider_dispatch={"provider_dispatch": True},
        spend_runtime_request={"runtime_request": "r"},
        click_sealed_execution={"status": "ready"},
        spend_sealed_execution={"status": "ready"},
    )
    assert consistent["consistent"] and consistent["margin_minor"] == 1500
