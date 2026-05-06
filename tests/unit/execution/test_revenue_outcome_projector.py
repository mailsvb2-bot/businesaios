from __future__ import annotations

from execution.revenue_outcome import RevenueOutcomeProjector


def test_revenue_outcome_projector_extracts_payment_outcome() -> None:
    projector = RevenueOutcomeProjector()
    payload = projector.project(
        feedback={
            "revenue": 250.0,
            "verified": True,
            "evidence_status": "payments",
            "evidence": {
                "payload": {
                    "connector_result": {"payment_id": "pay-1", "order_id": "ord-1"},
                },
            },
        }
    )
    assert payload["outcome_kind"] == "payment"
    assert payload["payment_id"] == "pay-1"
    assert payload["closed_loop"] is True
