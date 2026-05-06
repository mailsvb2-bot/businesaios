from pathlib import Path

from execution.closed_loop_orchestrator import ClosedLoopCycleInput, ClosedLoopOrchestrator


def _cycle(world_state):
    return ClosedLoopCycleInput(
        action={
            'action_type': 'publish_page',
            'action_id': 'econ-resume-1',
            'decision_id': 'dec-resume-1',
            'run_id': 'run-resume-1',
            'channel': 'web',
        },
        world_state=world_state,
        execution_receipt={'status': 'executed', 'decision_id': 'dec-resume-1'},
        feedback={'evidence': {'router_result': {'verified': True, 'status': 'verified', 'external_refs': ['page:1']}}},
        requested_tier='supervised',
        current_tier='supervised',
    )


def test_economic_restart_resume_flow_uses_persistent_backends_without_duplication(tmp_path: Path) -> None:
    root = tmp_path / 'runtime_data'
    first = ClosedLoopOrchestrator(economic_storage_root=root)
    first_result = first.run_cycle(cycle_input=_cycle({'meta': {}}))

    restarted = ClosedLoopOrchestrator(economic_storage_root=root)
    second_result = restarted.run_cycle(cycle_input=_cycle(first_result.world_state))

    payload = second_result.persisted_memory_evidence
    audit = payload['economic_cross_run_audit']
    assert audit['total_feedback_events'] == 1
    assert audit['snapshot_count'] == 1
    assert audit['duplicate_feedback_events'] == 0
    assert audit['duplicate_roi_events'] == 0
    assert audit['restart_resume_consistent'] is True
    assert second_result.world_state['meta']['economic_cross_run_audit']['total_feedback_events'] == 1
