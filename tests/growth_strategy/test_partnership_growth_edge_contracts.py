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


class _SingularPartnerLLM:
    def generate_sync(self, _request):
        return _Response(
            json.dumps(
                [
                    {
                        "stage": "referral",
                        "channel": "partnership",
                        "title": "Singular partner alias",
                        "mechanism": "Test a partner channel.",
                        "expected_impact": "+5% leads",
                        "effort": "low",
                        "risk": "low",
                        "metric": "leads",
                        "horizon_days": 14,
                        "action_hints": {"type": "partner_acquisition", "executable_actions": ["send"]},
                    }
                ]
            )
        )


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


def test_singular_partner_alias_is_canonicalized_before_safety_and_exclusion(tmp_path: Path) -> None:
    with SqliteEventStore(str(tmp_path / "alias.db")) as store:
        svc = GrowthStrategyService(event_store=store, llm=_SingularPartnerLLM())
        allowed = svc.generate_backlog(
            tenant_id="t1",
            user_id="u1",
            decision_id="alias-allowed-d",
            correlation_id="alias-allowed-c",
            goal=GrowthGoalV1(primary_stage="referral"),
        )
        partners = [h for h in allowed.top_hypotheses if h.channel == "partnerships"]
        assert len(partners) == 1
        assert partners[0].action_hints["advisory_only"] is True
        assert "type" not in partners[0].action_hints
        assert "executable_actions" not in partners[0].action_hints

        excluded = svc.generate_backlog(
            tenant_id="t1",
            user_id="u1",
            decision_id="alias-excluded-d",
            correlation_id="alias-excluded-c",
            goal=GrowthGoalV1(primary_stage="referral", constraints=("must not use partnerships",)),
        )
        assert excluded.top_hypotheses
        assert all(h.channel != "partnerships" for h in excluded.top_hypotheses)


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
        "must not use partnerships",
        "avoid partnerships",
        "avoid using partnerships",
        "exclude all partnerships",
        "without partnerships",
        "partnerships are prohibited",
        "избегать партнёрств",
        "исключить все партнерства",
        "не использовать партнёрства",
        "без партнеров",
        "никаких партнёрств",
        "партнёрства запрещены",
    ):
        assert policy.partnership_constraints_exclude((constraint,))
