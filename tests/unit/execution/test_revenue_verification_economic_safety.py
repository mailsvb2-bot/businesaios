from types import SimpleNamespace

from execution.revenue_verification import RevenueVerification


def test_revenue_verification_accepts_feedback_only_external_evidence() -> None:
    verifier = RevenueVerification()
    feedback = {
        "verified": True,
        "verification_status": "verified",
        "evidence": {
            "payload": {
                "connector_result": {
                    "payment_id": "pay_123",
                    "revenue_amount": 1250.0,
                    "currency": "EUR",
                    "status": "verified",
                    "confidence": 0.98,
                    "external_refs": ["pay_123"],
                }
            }
        },
    }

    result = verifier.verify(action_type="capture_payment", feedback=feedback, action_result=None)

    assert result.verified is True
    assert result.verification_status == "revenue_verified"
    assert result.outcome_kind == "payment"
    assert result.revenue_reference == "pay_123"
    assert result.currency == "EUR"
    assert result.metadata["evidence_mode"] == "external_only"


def test_revenue_verification_combines_execution_and_external_evidence() -> None:
    verifier = RevenueVerification()
    action_result = SimpleNamespace(action_id="a1", payload={"ok": True, "status": "executed", "currency": "USD"})
    feedback = {
        "verified": True,
        "verification_status": "verified",
        "evidence": {
            "payload": {
                "connector_result": {
                    "invoice_id": "inv_1",
                    "revenue_amount": 100.0,
                    "status": "verified",
                }
            }
        },
    }

    result = verifier.verify(action_type="issue_invoice", feedback=feedback, action_result=action_result)

    assert result.verified is True
    assert result.metadata["evidence_mode"] == "execution_and_external"
