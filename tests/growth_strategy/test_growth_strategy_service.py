from __future__ import annotations

import json
import time
from pathlib import Path

from core.growth.strategy.contracts import GROWTH_PARTNERSHIP_VISIBILITY_NOTE, GrowthGoalV1
from core.growth.strategy.service import GrowthStrategyService
from core.growth.strategy.signals import build_signals
from runtime.handler_impl.growth_strategy_generate import _render_plan, _visible_hypotheses
from runtime.platform.event_store.sqlite_event_store import SqliteEventStore


class _LLMResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class _UnrelatedGrowthLLM:
    def generate_sync(self, _request):
        return _LLMResponse(
            json.dumps(
                [
                    {
                        "stage": "activation",
                        "channel": "telegram",
                        "title": "Existing LLM hypothesis",
                        "mechanism": "Test a shorter activation path with measured conversion evidence.",
                        "expected_impact": "+5% conversion in 14 days",
                        "effort": "low",
                        "risk": "low",
                        "metric": "conversion_lead_to_purchase_pct",
                        "horizon_days": 14,
                        "action_hints": {"type": "messaging_flow"},
                    }
                ]
            )
        )


class _UnsafePartnerLLM:
    def generate_sync(self, _request):
        partner = {
            "stage": "referral",
            "channel": "partnerships",
            "title": "Existing partner idea",
            "mechanism": "Test a partner channel against measurable lead evidence.",
            "expected_impact": "+5% leads in 14 days",
            "effort": "low",
            "risk": "low",
            "metric": "leads",
            "horizon_days": 14,
            "action_hints": {
                "type": "partner_acquisition",
                "executable_actions": ["send"],
                "provider": "vk",
                "contact_target": "somebody",
                "evidence_key": "also_not_authoritative",
            },
        }
        return _LLMResponse(json.dumps([partner, {**partner, "title": "Duplicate partner idea"}]))


class _FullHighScoreLLM:
    def generate_sync(self, _request):
        return _LLMResponse(
            json.dumps(
                [
                    {
                        "stage": "revenue",
                        "channel": "meta_ads",
                        "title": f"High score hypothesis {index}",
                        "mechanism": "Use data from a controlled A/B experiment and attribution evidence to validate the change before rollout.",
                        "expected_impact": "+50% profit in 14 days",
                        "effort": "low",
                        "risk": "low",
                        "metric": "profit_minor",
                        "horizon_days": 14,
                        "action_hints": {},
                    }
                    for index in range(8)
                ]
            )
        )


def test_generate_backlog_fallback_creates_hypotheses(tmp_path: Path):
    db = tmp_path / "events.db"
    with SqliteEventStore(str(db)) as store:
        svc = GrowthStrategyService(event_store=store, llm=None)
        plan = svc.generate_backlog(tenant_id="t1", user_id="u1", decision_id="d1", correlation_id="c1", n=4)
        assert plan.tenant_id == "t1"
        assert len(plan.top_hypotheses) >= 2
        assert all(h.channel != "partnerships" for h in plan.top_hypotheses)

        backlog = svc.backlog(tenant_id="t1", limit=20)
        assert len(backlog) >= 2
        h, s, state = backlog[0]
        assert h.hypothesis_id
        assert state in {"new", "accepted", "rejected", "archived"}
        assert s is None or s.hypothesis_id == h.hypothesis_id


def test_zero_budget_goal_adds_partnership_through_canonical_growth_owner(tmp_path: Path):
    zero_budget_constraints = (
        "бюджет 0",
        "бюджет: 0,00",
        "budget 0",
        "budget: 0",
        "budget = 0",
        "budget=0.00",
    )
    with SqliteEventStore(str(tmp_path / "partner.db")) as store:
        svc = GrowthStrategyService(event_store=store, llm=None)
        for index, constraint in enumerate(zero_budget_constraints):
            plan = svc.generate_backlog(
                tenant_id="t1",
                user_id="u1",
                decision_id=f"partner-d{index}",
                correlation_id=f"partner-c{index}",
                goal=GrowthGoalV1(
                    primary_stage="acquisition",
                    horizon_days=14,
                    constraints=(constraint, "цель 300 регистраций"),
                ),
            )
            partners = [h for h in plan.top_hypotheses if h.channel == "partnerships"]
            assert len(partners) == 1
            hints = partners[0].action_hints
            assert hints["intent"] == "partnership_opportunity"
            assert hints["advisory_only"] is True
            assert hints["discovery_mode"] == "read_only"
            assert hints["decision_core_required"] is True
            assert hints["runtime_executor_required"] is True
            assert hints["separate_decision_per_external_contact"] is True
            assert hints["contact_policy_required"] is True
            assert hints["followup_requires_delivery_and_no_reply_evidence"] is True
            assert "type" not in hints
            assert "executable_actions" not in hints

        paid_plan = svc.generate_backlog(
            tenant_id="t1",
            user_id="u1",
            decision_id="partner-paid",
            correlation_id="partner-paid-c",
            goal=GrowthGoalV1(primary_stage="acquisition", constraints=("budget 0.5",)),
        )
        assert all(h.channel != "partnerships" for h in paid_plan.top_hypotheses)


def test_explicit_partnership_exclusion_overrides_referral_and_zero_budget(tmp_path: Path):
    with SqliteEventStore(str(tmp_path / "partner-excluded.db")) as store:
        svc = GrowthStrategyService(event_store=store, llm=None)
        goals = (
            GrowthGoalV1(primary_stage="referral", constraints=("no partnerships",)),
            GrowthGoalV1(primary_stage="acquisition", constraints=("budget 0", "без партнёров")),
            GrowthGoalV1(primary_stage="acquisition", constraints=("zero paid", "не использовать партнерства")),
        )
        for index, goal in enumerate(goals):
            plan = svc.generate_backlog(
                tenant_id="t1",
                user_id="u1",
                decision_id=f"excluded-d{index}",
                correlation_id=f"excluded-c{index}",
                goal=goal,
            )
            assert all(h.channel != "partnerships" for h in plan.top_hypotheses)

        llm_plan = GrowthStrategyService(event_store=store, llm=_UnsafePartnerLLM()).generate_backlog(
            tenant_id="t1",
            user_id="u1",
            decision_id="excluded-llm-d",
            correlation_id="excluded-llm-c",
            goal=GrowthGoalV1(primary_stage="referral", constraints=("without partnerships",)),
        )
        assert all(h.channel != "partnerships" for h in llm_plan.top_hypotheses)


def test_llm_cannot_drop_relevant_partnership_hypothesis(tmp_path: Path):
    with SqliteEventStore(str(tmp_path / "partner-llm.db")) as store:
        svc = GrowthStrategyService(event_store=store, llm=_UnrelatedGrowthLLM())
        plan = svc.generate_backlog(
            tenant_id="t1",
            user_id="u1",
            decision_id="partner-d2",
            correlation_id="partner-c2",
            goal=GrowthGoalV1(
                primary_stage="referral",
                horizon_days=21,
                constraints=("приоритет — партнёрства",),
            ),
        )
        assert any(h.title == "Existing LLM hypothesis" for h in plan.top_hypotheses)
        partners = [h for h in plan.top_hypotheses if h.channel == "partnerships"]
        assert len(partners) == 1
        assert partners[0].stage == "referral"
        assert partners[0].action_hints["advisory_only"] is True


def test_required_partnership_visibility_is_a_render_projection_not_ranking_override(tmp_path: Path):
    with SqliteEventStore(str(tmp_path / "partner-visible.db")) as store:
        svc = GrowthStrategyService(event_store=store, llm=_FullHighScoreLLM())
        plan = svc.generate_backlog(
            tenant_id="t1",
            user_id="u1",
            decision_id="partner-visible-d",
            correlation_id="partner-visible-c",
            goal=GrowthGoalV1(primary_stage="referral"),
            n=8,
        )
        assert len(plan.top_hypotheses) == 9
        assert sum(h.title.startswith("High score hypothesis") for h in plan.top_hypotheses) == 8
        assert all(h.channel != "partnerships" for h in plan.top_hypotheses[:8])
        assert plan.top_hypotheses[8].channel == "partnerships"
        assert GROWTH_PARTNERSHIP_VISIBILITY_NOTE in plan.notes

        visible = _visible_hypotheses(plan, limit=8)
        assert len(visible) == 8
        assert any(h.channel == "partnerships" for h in visible)
        rendered = _render_plan(plan)
        assert "[referral/partnerships]" in rendered
        assert "High score hypothesis 0" in rendered
        assert "High score hypothesis 7" not in rendered
        assert len(plan.top_hypotheses) == 9
        assert plan.top_hypotheses[8].channel == "partnerships"


def test_llm_partnership_cannot_smuggle_executable_authority(tmp_path: Path):
    with SqliteEventStore(str(tmp_path / "partner-unsafe-llm.db")) as store:
        svc = GrowthStrategyService(event_store=store, llm=_UnsafePartnerLLM())
        plan = svc.generate_backlog(
            tenant_id="t1",
            user_id="u1",
            decision_id="partner-safe-d",
            correlation_id="partner-safe-c",
            goal=GrowthGoalV1(primary_stage="referral"),
        )
        partners = [h for h in plan.top_hypotheses if h.channel == "partnerships"]
        assert len(partners) == 1
        assert partners[0].title == "Existing partner idea"
        hints = partners[0].action_hints
        assert set(hints) == {
            "intent",
            "advisory_only",
            "discovery_mode",
            "decision_core_required",
            "runtime_executor_required",
            "separate_decision_per_external_contact",
            "contact_policy_required",
            "followup_requires_delivery_and_no_reply_evidence",
        }
        assert hints["advisory_only"] is True
        assert hints["decision_core_required"] is True


def test_accept_reject_updates_state(tmp_path: Path):
    db = tmp_path / "events.db"
    with SqliteEventStore(str(db)) as store:
        svc = GrowthStrategyService(event_store=store, llm=None)
        plan = svc.generate_backlog(tenant_id="t1", user_id="u1", decision_id="d1", correlation_id="c1", n=3)
        hid = plan.top_hypotheses[0].hypothesis_id

        svc.accept_hypothesis(tenant_id="t1", user_id="u1", decision_id="d2", correlation_id="c2", hypothesis_id=hid)
        backlog = svc.backlog(tenant_id="t1", limit=10)
        states = {h.hypothesis_id: st for (h, _, st) in backlog}
        assert states.get(hid) == "accepted"

        svc.reject_hypothesis(tenant_id="t1", user_id="u1", decision_id="d3", correlation_id="c3", hypothesis_id=hid)
        backlog2 = svc.backlog(tenant_id="t1", limit=10)
        states2 = {h.hypothesis_id: st for (h, _, st) in backlog2}
        assert states2.get(hid) == "rejected"


def test_sales_funnel_replays_hard_tenant_evidence(tmp_path: Path):
    now = int(time.time() * 1000)
    with SqliteEventStore(str(tmp_path / "sales.db")) as store:
        rows = (
            ("t1", "lead-1", "sales_qualified", {"source": "telegram"}),
            ("t1", "lead-1", "sales_declined", {"source": "telegram"}),
            ("t1", "lead-1", "purchase_completed@v1", {"source": "telegram"}),
            ("t1", "operator", "sales_qualification_failed", {"subject_id": "lead-2", "source": "website"}),
            ("t2", "other", "purchase_completed@v1", {"source": "telegram"}),
        )
        for index, (tenant, user, kind, payload) in enumerate(rows):
            store.append_event({"tenant_id": tenant, "timestamp_ms": now - 5000 + index, "user_id": user, "event_type": kind, "payload": payload})
        total = build_signals(store, tenant_id="t1").sales_funnel["total"]
        assert total["discovered"] == 2 and total["qualified"] == 1 and total["won"] == 1 and total["lost"] == 1
