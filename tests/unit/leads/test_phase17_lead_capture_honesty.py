from __future__ import annotations

from leads import LeadRouter
from leads.lead_capture_facade import LeadCaptureFacade


def test_lead_capture_facade_is_honest_capture_surface() -> None:
    result = LeadCaptureFacade().capture({"lead_id": "L1"})
    assert result == {
        "kind": "lead_capture",
        "payload": {
            "lead_id": "L1",
            "mode": "capture_only",
            "decision_path": "demand_decision_required",
        },
    }

def test_lead_router_is_only_a_compatibility_alias() -> None:
    result = LeadRouter().route({"lead_id": "L2"})
    assert result["kind"] == "lead_capture"
    assert result["payload"]["mode"] == "capture_only"
    assert result["payload"]["decision_path"] == "demand_decision_required"
