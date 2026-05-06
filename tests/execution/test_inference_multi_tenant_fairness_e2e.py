from execution.inference_fairness_scheduler import InferenceFairnessScheduler


def test_inference_fairness_scheduler_prevents_starvation_under_skew():
    slots = InferenceFairnessScheduler().allocate([
        {'tenant_id': 'tenant-a', 'queue_depth': 1000},
        {'tenant_id': 'tenant-b', 'queue_depth': 1},
        {'tenant_id': 'tenant-c', 'queue_depth': 1},
    ])
    shares = {slot.tenant_id: slot.allocated_share for slot in slots}
    assert shares['tenant-b'] > 0.0
    assert shares['tenant-c'] > 0.0
    assert round(sum(shares.values()), 6) == 1.0
