from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.experiments.guardrails import CanaryDecision, GuardrailResult
from runtime.experiments.hooks import record_live_canary_executor_result
from runtime.proofs import ACTION_PROOF_EVENT


class FakeLedger:
    def __init__(self, proof_payload: dict | None = None) -> None:
        self.assignment = {
            "eligible": True,
            "tenant_id": "tenant-a",
            "arm": "candidate",
        }
        self.proof_payload = {"action": "noop@v1", **(proof_payload or {})}

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
                "payload": dict(self.proof_payload),
            }
        ]


def _runtime(*, proof_payload: dict | None = None):
    recorded_executions: list[dict] = []
    opened_circuits: list[tuple[str, ...]] = []
    rollback_requests: list[dict] = []
    coordinator = SimpleNamespace(
        ledger=FakeLedger(proof_payload),
        candidate_policy_id="candidate@v2",
        policy=SimpleNamespace(experiment_id="execution-cost"),
        record_execution=lambda **kwargs: recorded_executions.append(kwargs),
        _guard_result=lambda: GuardrailResult(
            CanaryDecision.CONTINUE,
            ("healthy",),
            {},
        ),
        _open_local_circuit=lambda result, **_kwargs: opened_circuits.append(
            tuple(result.reasons)
        ),
    )
    executor = SimpleNamespace(
        _decision_core=SimpleNamespace(_live_canary=coordinator),
        _live_canary_rollback_submitter=lambda **kwargs: rollback_requests.append(
            kwargs
        ),
    )
    return executor, recorded_executions, opened_circuits, rollback_requests


def _env(*, expected_cost: float):
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-1",
            correlation_id="correlation-1",
            action="noop@v1",
            payload={"expected_cost": expected_cost},
        )
    )


@pytest.mark.parametrize("actual_cost", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_result_cost_forces_governed_rollback(actual_cost: float) -> None:
    executor, recorded, circuits, rollbacks = _runtime()

    record_live_canary_executor_result(
        executor=executor,
        env=_env(expected_cost=1.0),
        result=SimpleNamespace(ok=True, output={"cost": actual_cost}, error=None),
    )

    assert recorded == []
    assert circuits == [("execution_evidence_error:RuntimeError",)]
    assert len(rollbacks) == 1


@pytest.mark.parametrize("proof_cost", [float("nan"), float("inf"), -1.0])
def test_invalid_exact_provider_proof_cost_forces_rollback(proof_cost: float) -> None:
    executor, recorded, circuits, rollbacks = _runtime(
        proof_payload={"cost": proof_cost}
    )

    record_live_canary_executor_result(
        executor=executor,
        env=_env(expected_cost=1.0),
        result=SimpleNamespace(ok=True, output={}, error=None),
    )

    assert recorded == []
    assert circuits == [("execution_evidence_error:RuntimeError",)]
    assert len(rollbacks) == 1


def test_verified_actual_cost_replaces_larger_reservation() -> None:
    executor, recorded, circuits, rollbacks = _runtime(
        proof_payload={"cost": 10.0}
    )

    assert ACTION_PROOF_EVENT["noop@v1"]
    record_live_canary_executor_result(
        executor=executor,
        env=_env(expected_cost=80.0),
        result=SimpleNamespace(ok=True, output={"cost": 10.0}, error=None),
    )

    assert len(recorded) == 1
    assert recorded[0]["cost"] == 10.0
    assert circuits == []
    assert rollbacks == []
