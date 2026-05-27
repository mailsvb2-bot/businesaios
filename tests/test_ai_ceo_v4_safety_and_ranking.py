from __future__ import annotations

from dataclasses import dataclass

from application.decision_policy.safety import gate_decision_action
from core.ai.action_ranking import rank_proposals


@dataclass
class Proposal:
    action: str
    payload: dict


class DummyEventLog:
    def query_recent(self, event_type: str, since_ms: int, filters: dict):
        return []


def test_rank_proposals_prefers_higher_expected_profit():
    props = [
        Proposal(action="a@v1", payload={"expected_profit_delta_minor": 10}),
        Proposal(action="b@v1", payload={"expected_profit_delta_minor": 50}),
    ]
    ranked = rank_proposals(props)
    assert ranked[0].action == "b@v1"


def test_gate_allows_low_impact_by_default(monkeypatch):
    monkeypatch.delenv("AI_CEO_HIGH_IMPACT_ROLLOUT_PCT", raising=False)
    monkeypatch.delenv("AI_CEO_BLAST_RADIUS_MAX_PER_HOUR", raising=False)
    ok, reason, dbg = gate_decision_action(
        action="send_message@v1",
        payload={},
        tenant_id="t1",
        user_id="u1",
        event_log=DummyEventLog(),
    )
    assert ok
    assert reason == "ok"
