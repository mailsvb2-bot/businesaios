from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_runtime_replay_surface_is_thin_and_non_deciding() -> None:
    text = (ROOT / "runtime" / "replay.py").read_text(encoding="utf-8")
    assert "CANON_RUNTIME_REPLAY_THIN_SURFACE = True" in text
    assert "CANON_RUNTIME_REPLAY_NO_DECISION_LOGIC = True" in text
    assert "DecisionEnvelope" in text


def test_phase15_historical_replay_is_snapshot_bound_and_non_effectful() -> None:
    text = (ROOT / "runtime" / "replay.py").read_text(encoding="utf-8")
    assert "CANON_PHASE15_HISTORICAL_REPLAY = True" in text
    assert "CANON_PHASE15_NO_FUTURE_LEAKAGE = True" in text
    assert "decision.snapshot_id" in text
    assert "decision.state_hash" in text
    assert "self._policy_registry" in text
    assert "maybe_get" in text
    assert "HISTORICAL_REPLAY_CANDIDATE_NOT_REGISTERED" in text
    assert "HISTORICAL_REPLAY_FUTURE_STATE" in text
    for forbidden in (
        "execute_autopilot(",
        ".decide(",
        ".optimize(",
        ".issue(",
        ".emit(",
        ".put(",
        "enrich_state_with_world_model(",
    ):
        assert forbidden not in text


def test_phase15_replay_accepts_candidate_identity_not_arbitrary_policy_object() -> None:
    text = (ROOT / "runtime" / "replay.py").read_text(encoding="utf-8")
    assert "candidate_policy_id: str" in text
    assert "candidate_policy: Any" not in text
