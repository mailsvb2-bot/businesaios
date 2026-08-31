from __future__ import annotations

from application.evidence.evidence_persistence import EvidencePersistenceService
from reliability.outbox_store import InMemoryOutboxStore


def test_feedback_artifacts_scope_reliability_from_verification_context() -> None:
    outbox = InMemoryOutboxStore()
    service = EvidencePersistenceService(outbox_store=outbox)
    verification_result = {
        "context": {
            "action": {
                "tenant_id": "tenant-1",
                "business_id": "business-1",
                "run_id": "run-1",
                "intent_id": "intent:dec-1",
                "decision_id": "dec-1",
                "action_id": "action:dec-1",
                "action_type": "send_message",
            },
            "execution_receipt": {
                "executed": True,
                "action_id": "action:dec-1",
                "action_type": "send_message",
            },
        },
        "verification": {"status": "verified", "verified": True},
        "verified": True,
    }

    artifacts = service.build_feedback_artifacts(verification_result=verification_result)

    persisted = artifacts["persisted_outcome"]
    assert persisted["tenant_id"] == "tenant-1"
    assert persisted["business_id"] == "business-1"
    receipt = artifacts["persistence_receipt"]
    message = outbox.get(tenant_id="tenant-1", message_id=receipt["outbox_message_id"])
    assert message is not None
    assert message.tenant_id == "tenant-1"
    assert message.run_id == "run-1"
    assert message.payload["business_id"] == "business-1"
    assert message.payload["run_id"] == "run-1"
    assert message.payload["action_id"] == "action:dec-1"
