from __future__ import annotations


class LeadCaptureFacade:
    """Honest lead-intake facade.

    This surface captures lead intake only. It does not perform real
    routing/orchestration and must not pretend to select a final decision.
    """

    def capture(self, payload: dict) -> dict:
        row = dict(payload)
        row["mode"] = "capture_only"
        row["decision_path"] = "demand_decision_required"
        return {"kind": "lead_capture", "payload": row}

    def route(self, payload: dict) -> dict:
        return self.capture(payload)


LeadRouter = LeadCaptureFacade

__all__ = ("LeadCaptureFacade", "LeadRouter")
