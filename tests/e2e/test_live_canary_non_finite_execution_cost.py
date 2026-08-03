from __future__ import annotations

from types import SimpleNamespace

import pytest

from runtime.experiments.hooks import record_live_canary_executor_result
from runtime.proofs import ACTION_PROOF_EVENT


class FakeLedger:
    def __init__(self) -> None:
        self.assignment = {
            "eligible": True,
            "tenant_id": "tenant-a",
            "arm": "candidate",
        }

    def assignment_for_decision(self, _decision_id: str):
        return dict(self.assignment)

    def events_for_decision(self, decision_id: str, event_type: str):
        return [
            {
                "event_id": "provider-proof-1",
                "tenant_id": "tenant-a",
                "source": "runtime_executor",
                "event_type": event_type,
                "decision_id": decision_id,
                "payload": {"action": "noop@v1"},
            }
        ]


@pytest.mark.parametrize("actual_cost", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_provider_cost_forces_governed_rollback(actual_cost: float) -> None:
    recorded_executions: list[dict] = []
    opened_circuits: list[tuple[str, ...]] = []
    rollback_requests: list[dict] = []
    ledger = FakeLedger()
    coordinator = SimpleNamespace(
        ledger=ledger,
        candidate_policy_id="candidate@v2",
        policy=SimpleNamespace(experiment_id="non-finite-cost"),
        record_execution=lambda **kwargs: recorded_executions.append(kwargs),
        _open_local_circuit=lambda result, **_kwargs: opened_circuits.append(
            tuple(result.reasons)
        ),
    )
    decision_core = SimpleNamespace(_live_canary=coordinator)
    executor = SimpleNamespace(
        _decision_core=decision_core,
        _live_canary_rollback_submitter=lambda **kwargs: rollback_requests.append(
            kwargs
        ),
    )
    env = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-1",
            correlation_id="correlation-1",
            action="noop@v1",
            payload={"expected_cost": 1.0},
        )
    )
    result = SimpleNamespace(
        ok=True,
        output={"cost": actual_cost},
        error=None,
    )

    assert ACTION_PROOF_EVENT["noop@v1"]
    record_live_canary_executor_result(
        executor=executor,
        env=env,
        result=result,
    )

    assert recorded_executions == []
    assert opened_circuits == [("execution_evidence_error:RuntimeError",)]
    assert len(rollback_requests) == 1
    assert rollback_requests[0]["candidate_policy_id"] == "candidate@v2"
    assert rollback_requests[0]["experiment_id"] == "non-finite-cost"
