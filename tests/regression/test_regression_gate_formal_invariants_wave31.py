from __future__ import annotations

from formal.proof_obligations.invariants import DecisionObservation, validate_observation_invariants
from formal.regression_gate.canonical_observation import CanonicalObservation


def test_formal_invariants_accept_canonical_executed_observation() -> None:
    obs = DecisionObservation(
        source="DecisionCore",
        status="executed",
        governance_called=True,
        executor_called=True,
        events=("decision.evaluated", "decision.executed"),
        metrics=("decision.latency_ms", "decision.count"),
        traces=("decision.trace",),
        payload=CanonicalObservation.from_mapping({"status": "executed", "action_type": "DemoAction"}).payload,
    )
    assert validate_observation_invariants(obs) == []


def test_formal_invariants_reject_hidden_bypass_execution() -> None:
    obs = DecisionObservation(
        source="AdapterShortcut",
        status="executed",
        governance_called=False,
        executor_called=True,
        events=("decision.evaluated", "decision.executed"),
        metrics=("decision.latency_ms",),
        traces=(),
        payload={"status": "executed", "action_type": "DemoAction"},
    )
    errors = validate_observation_invariants(obs)
    assert errors
    assert any("DecisionCore" in error for error in errors)
    assert any("bypassed governance" in error for error in errors)
