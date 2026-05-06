from __future__ import annotations

from execution.closed_loop_orchestrator import ClosedLoopCycleInput, ClosedLoopOrchestrator


def test_closed_loop_trace_carries_fencing_and_leader_metadata() -> None:
    orchestrator = ClosedLoopOrchestrator()
    result = orchestrator.run_cycle(
        cycle_input=ClosedLoopCycleInput(
            action={'action_type': 'publish', 'action_id': 'a-1', 'decision_id': 'd-1'},
            execution_receipt={
                'decision_id': 'd-1',
                'leader_election': {'election_name': 'runtime-scheduler', 'leader_id': 'node-a'},
                'fencing_token': 7,
            },
        )
    )

    assert result.reliability_trace['leader_election_name'] == 'runtime-scheduler'
    assert result.reliability_trace['leader_id'] == 'node-a'
    assert result.reliability_trace['fencing_token'] == 7
    assert result.next_tier_context['closed_loop_trace_key'] == result.reliability_trace['trace_key']
