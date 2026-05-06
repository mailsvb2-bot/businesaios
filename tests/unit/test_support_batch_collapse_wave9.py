from __future__ import annotations

from runtime.platform.support.contracts.action import Action
from runtime.platform.support.contracts.promotion_contract import PromotionDecision
from runtime.platform.support.events.event_bus import EventBus
from runtime.platform.support.governance.approval_workflow import ApprovalWorkflow
from runtime.platform.support.observability.business.kpi_metrics import KPIMetrics
from runtime.platform.support.security.auth import Auth


def test_support_contracts_and_events_survive_batch_collapse() -> None:
    action = Action(name="ping", payload={"ok": True})
    decision = PromotionDecision(candidate_id="c1", approved=True, reason="ok")
    bus = EventBus()
    bus.publish("topic", {"action": action.name, "approved": decision.approved})
    assert bus.events("topic") == [{"action": "ping", "approved": True}]


def test_support_governance_observability_and_security_imports_work() -> None:
    assert ApprovalWorkflow().approved([True, True]) is True
    assert KPIMetrics().summarize(3.0) == {"kpi": 3.0}
    assert Auth().authenticated("token") is True
