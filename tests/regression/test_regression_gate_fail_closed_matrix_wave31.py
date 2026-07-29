from __future__ import annotations

from types import SimpleNamespace

from config.execution_contract import CANONICAL_DECISION_PATH, CANONICAL_OPTIMIZATION_TARGET
from core.actions.names import ACTION_ROUTE_LEAD_V1
from demand_decision.canonical_decision_bridge import CanonicalDemandDecisionBridge


class _RejectingDecisionIssuer:
    def issue(self, state):
        route = dict(getattr(state, "meta", {}).get("demand_route") or {})
        candidates = tuple(route.get("candidates") or ())
        reason = "no_safe_candidates" if not candidates else "decision_core_rejected_all_candidates"
        return SimpleNamespace(
            decision=SimpleNamespace(
                action=ACTION_ROUTE_LEAD_V1,
                decision_id="d-1",
                correlation_id=str(route.get("request_id") or "d-1"),
                payload={
                    "request_id": str(route.get("request_id") or ""),
                    "selected_business_id": None,
                    "runner_up_business_ids": [],
                    "requires_manual_review": True,
                    "candidate_count": len(candidates),
                    "blocked_candidate_count": int(route.get("blocked_candidate_count") or 0),
                    "manual_review_reason": reason,
                },
            )
        )


class _RoutingCandidate:
    def __init__(self, business_id: str, rank_score: float, blocked: bool = False) -> None:
        self.business_id = business_id
        self.rank_score = rank_score
        self.blocked = blocked
        self.trace = {"adjusted_score": rank_score, "match_score": rank_score}


class _Request:
    def __init__(self, request_id: str) -> None:
        self.request_id = request_id
        self.customer_id = "cust-1"


def test_bridge_fail_closed_when_no_safe_candidates_exist() -> None:
    bridge = CanonicalDemandDecisionBridge(decision_core=_RejectingDecisionIssuer())
    decision = bridge.issue(
        request=_Request("req-1"),
        routing_preparation={
            "request_id": "req-1",
            "ranked_candidates": (),
            "requires_manual_review": True,
            "trace": {"request_id": "req-1"},
        },
    )
    assert decision.requires_manual_review is True
    assert decision.selected_business_id is None
    assert decision.trace["decision_path"] == CANONICAL_DECISION_PATH
    assert decision.trace["optimization_target"] == CANONICAL_OPTIMIZATION_TARGET
    assert decision.trace["manual_review_reason"] == "no_safe_candidates"


def test_bridge_fail_closed_when_decision_core_rejects_all_candidates() -> None:
    bridge = CanonicalDemandDecisionBridge(decision_core=_RejectingDecisionIssuer())
    decision = bridge.issue(
        request=_Request("req-1"),
        routing_preparation={
            "request_id": "req-1",
            "ranked_candidates": (_RoutingCandidate("biz-1", 0.9),),
            "trace": {"request_id": "req-1", "preferred_channels": {"biz-1": "telegram"}},
        },
    )
    assert decision.requires_manual_review is True
    assert decision.selected_business_id is None
    assert decision.trace["decision_path"] == CANONICAL_DECISION_PATH
    assert decision.trace["manual_review_reason"] == "decision_core_rejected_all_candidates"
