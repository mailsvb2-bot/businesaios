from execution.closed_loop_orchestrator import ClosedLoopCycleInput, ClosedLoopOrchestrator
from execution.economic_memory_store import InMemoryEconomicMemoryStore
from execution.replay_safe_roi_history import InMemoryROIHistoryStore, ReplaySafeROIHistoryBuilder
from observability.economic_policy_snapshot_store import InMemoryEconomicPolicySnapshotStore


def test_replay_safe_roi_history_builder_uses_event_id() -> None:
    record = ReplaySafeROIHistoryBuilder().build(
        event_id='evt-1',
        economic_feedback={
            'channel': 'ads',
            'action_type': 'launch_campaign',
            'expected_roi': 0.4,
            'realized_revenue': 120.0,
            'approved_budget': 80.0,
            'requested_budget': 100.0,
            'verified': True,
        },
        policy_snapshot={'snapshot_id': 'snap-1'},
    )
    payload = record.to_dict()
    assert payload['event_id'] == 'evt-1'
    assert payload['snapshot_id'] == 'snap-1'
    assert payload['verified'] is True


def test_closed_loop_persists_economic_memory_and_roi_history_without_replay_duplication() -> None:
    memory_store = InMemoryEconomicMemoryStore()
    roi_store = InMemoryROIHistoryStore()
    snapshot_store = InMemoryEconomicPolicySnapshotStore()
    orchestrator = ClosedLoopOrchestrator(
        economic_memory_store=memory_store,
        roi_history_store=roi_store,
        economic_policy_snapshot_store=snapshot_store,
    )
    cycle = ClosedLoopCycleInput(
        action={
            'action_type': 'publish_page',
            'action_id': 'econ-1',
            'decision_id': 'dec-1',
            'channel': 'web',
        },
        world_state={'meta': {}},
        execution_receipt={'status': 'executed'},
        feedback={'evidence': {'router_result': {'verified': True, 'status': 'verified', 'external_refs': ['page:1']}}},
        requested_tier='supervised',
        current_tier='supervised',
    )
    first = orchestrator.run_cycle(cycle_input=cycle)
    second = orchestrator.run_cycle(cycle_input=ClosedLoopCycleInput(
        action=cycle.action,
        world_state=first.world_state,
        execution_receipt=cycle.execution_receipt,
        feedback=cycle.feedback,
        requested_tier='supervised',
        current_tier='supervised',
    ))

    meta = second.world_state['meta']
    assert len(memory_store.list_rows()) == 1
    assert len(roi_store.list_rows()) == 1
    assert len(snapshot_store.list_rows()) == 1
    assert len(meta['economic_feedback_history']) == 1
    assert len(meta['economic_roi_history']) == 1
    assert len(meta['economic_policy_snapshot_history']) == 1
    assert second.persisted_memory_evidence['economic_feedback']['event_id']
    assert second.persisted_memory_evidence['economic_roi_history']['event_id'] == second.persisted_memory_evidence['economic_event_id']
