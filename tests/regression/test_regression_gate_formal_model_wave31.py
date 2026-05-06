from __future__ import annotations

from formal.proof_obligations.exhaustive_model import verify_runtime_decision_model
from formal.proof_obligations.smt_encoding import try_prove_runtime_decision_gate


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
