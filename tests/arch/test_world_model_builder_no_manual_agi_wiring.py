from __future__ import annotations

from pathlib import Path


def test_world_model_builder_contains_single_canonical_agi_switch() -> None:
    text = Path("bootstrap/world_model_builder.py").read_text(encoding="utf-8")
    assert "DecisionAGIWorldModel" in text
    assert "WORLD_MODEL_KIND" in text
    assert "DECISION_AGI_BASE_WORLD_MODEL_KIND" in text


def test_decision_core_does_not_manually_import_agi_world_model() -> None:
    text = Path("core/ai/decision_core.py").read_text(encoding="utf-8")
    assert "DecisionAGIWorldModel" not in text
    assert "decision_agi_world_model" not in text
