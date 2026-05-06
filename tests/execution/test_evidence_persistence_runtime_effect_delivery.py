from execution.evidence_persistence import EvidencePersistenceService


def test_evidence_persistence_attaches_runtime_effect_delivery() -> None:
    service = EvidencePersistenceService()
    receipt = service._attach_reliability_receipt(  # type: ignore[attr-defined]
        tenant_id="tenant-a",
        business_id="biz-1",
        run_id="run-1",
        step_index=0,
        action_id="act-1",
        action_type="send_email",
        verification_result={"verification": {"status": "verified"}},
        execution_result={"effect_delivery": {"guarantee": "runtime_outbox", "runtime_outbox_status": "delivered"}},
        receipt={"persistence_key": "pk-1", "persisted_at": "now"},
    )
    assert receipt["runtime_effect_delivery"]["guarantee"] == "runtime_outbox"
    assert receipt["delivery_guarantee"] == "exactly_once_effect_scope"
