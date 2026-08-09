from __future__ import annotations

import json
from pathlib import Path

from config.strategic_growth_policy import GrowthStrategyServicePolicy
from core.growth.strategy.contracts import GrowthGoalV1
from core.growth.strategy.service import GrowthStrategyService
from runtime.platform.event_store.sqlite_event_store import SqliteEventStore


class _Response:
    def __init__(self, content: str) -> None:
        self.content = content


class _DuplicatePartnerLLM:
    def generate_sync(self, _request):
        partner = {
            "stage": "referral",
            "channel": "partnerships",
            "title": "Partner idea",
            "mechanism": "Test partnership evidence.",
            "expected_impact": "+5% leads",
            "effort": "low",
            "risk": "low",
            "metric": "leads",
            "horizon_days": 14,
            "action_hints": {},
        }
        others = [
            {
                "stage": "revenue",
                "channel": "meta_ads",
                "title": f"Unique idea {index}",
                "mechanism": "Test a distinct measurable growth mechanism.",
                "expected_impact": "+5% profit",
                "effort": "low",
                "risk": "low",
                "metric": "profit_minor",
                "horizon_days": 14,
                "action_hints": {},
            }
            for index in range(7)
        ]
        return _Response(json.dumps([partner, {**partner, "title": "Duplicate partner"}, *others]))


class _PartnersOnlyLLM:
    def generate_sync(self, _request):
        row = {
            "stage": "referral",
            "channel": "partnerships",
            "title": "Partner only",
            "mechanism": "Partner-only proposal.",
            "expected_impact": "+5% leads",
            "effort": "low",
            "risk": "low",
            "metric": "leads",
            "horizon_days": 14,
            "action_hints": {},
        }
        return _Response(json.dumps([row, {**row, "title": "Partner only duplicate"}]))


def test_partner_dedup_happens_before_llm_result_limit(tmp_path: Path) -> None:
    with SqliteEventStore(str(tmp_path / "dedupe.db")) as store:
        plan = GrowthStrategyService(event_store=store, llm=_DuplicatePartnerLLM()).generate_backlog(
            tenant_id="t1",
            user_id="u1",
            decision_id="dedupe-d",
            correlation_id="dedupe-c",
            goal=GrowthGoalV1(primary_stage="referral"),
            n=8,
        )
        assert len(plan.top_hypotheses) == 8
        assert sum(h.channel == "partnerships" for h in plan.top_hypotheses) == 1
        assert sum(h.title.startswith("Unique idea") for h in plan.top_hypotheses) == 7


def test_partner_exclusion_refills_partner_only_llm_with_existing_fallback(tmp_path: Path) -> None:
    with SqliteEventStore(str(tmp_path / "refill.db")) as store:
        plan = GrowthStrategyService(event_store=store, llm=_PartnersOnlyLLM()).generate_backlog(
            tenant_id="t1",
            user_id="u1",
            decision_id="refill-d",
            correlation_id="refill-c",
            goal=GrowthGoalV1(primary_stage="referral", constraints=("do not use partnerships",)),
            n=8,
        )
        assert plan.top_hypotheses
        assert all(h.channel != "partnerships" for h in plan.top_hypotheses)
        assert any(h.channel != "partnerships" for h in plan.top_hypotheses)


def test_common_explicit_partner_prohibitions_are_fail_closed() -> None:
    policy = GrowthStrategyServicePolicy()
    for constraint in (
        "do not use partnerships",
        "don't use partnerships",
        "avoid partnerships",
        "exclude all partnerships",
        "without partnerships",
        "избегать партнёрств",
        "исключить все партнерства",
        "не использовать партнёрства",
        "без партнеров",
    ):
        assert policy.partnership_constraints_exclude((constraint,))
