from __future__ import annotations

from pathlib import Path

from formal.proof_obligations.exhaustive_model import verify_runtime_decision_model
from formal.proof_obligations.invariants import DecisionObservation, validate_observation_invariants
from formal.proof_obligations.smt_encoding import try_prove_runtime_decision_gate
from formal.regression_gate.canonical_observation import CanonicalObservation

ROOT = Path(__file__).resolve().parents[2]


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


def test_exhaustive_runtime_decision_model_finds_the_boundary_of_valid_cases() -> None:
    result = verify_runtime_decision_model()
    assert result["checked_cases"] == 32
    assert result["passing_cases"] < result["checked_cases"]
    assert result["failing_cases"]


def test_optional_smt_encoding_is_either_proved_or_explicitly_skipped() -> None:
    result = try_prove_runtime_decision_gate()
    assert "ok" in result
    if not result.get("skipped"):
        assert result["ok"] is True


def test_tla_runtime_decision_gate_assets_exist() -> None:
    spec = ROOT / "formal" / "tla" / "runtime_decision_gate.tla"
    cfg = ROOT / "formal" / "tla" / "runtime_decision_gate.cfg"
    assert spec.exists()
    assert cfg.exists()

    text = spec.read_text(encoding="utf-8")
    assert "NoBypass" in text
    assert "FailClosed" in text
    assert "ObservabilityComplete" in text
