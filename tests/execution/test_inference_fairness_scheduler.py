from execution.inference_fairness_scheduler import InferenceFairnessScheduler


def test_inference_fairness_scheduler_allocates_non_zero_share_per_tenant():
    scheduler = InferenceFairnessScheduler()
    slots = scheduler.allocate([{'tenant_id': 'a', 'queue_depth': 100}, {'tenant_id': 'b', 'queue_depth': 1}])
    assert len(slots) == 2
    assert all(slot.allocated_share > 0 for slot in slots)
    assert round(sum(slot.allocated_share for slot in slots), 6) == 1.0
