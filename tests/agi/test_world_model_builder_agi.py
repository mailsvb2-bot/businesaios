from __future__ import annotations

from bootstrap.canonical_decision_world_model import CanonicalDecisionWorldModel
from bootstrap.decision_agi_world_model import DecisionAGIWorldModel
from bootstrap.world_model_builder import build_default_world_model, describe_default_world_model


def test_world_model_builder_selects_decision_agi_adapter(monkeypatch):
    monkeypatch.setenv("WORLD_MODEL_KIND", "decision_agi@v1")
    monkeypatch.setenv("DECISION_AGI_BASE_WORLD_MODEL_KIND", "hybrid@v1")
    model = build_default_world_model()
    description = describe_default_world_model()
    assert isinstance(model, DecisionAGIWorldModel)
    assert isinstance(model, CanonicalDecisionWorldModel)
    assert description["implementation"] == "bootstrap.decision_agi_world_model.DecisionAGIWorldModel"
    assert description["kind"] == "decision_agi@v1"
    assert description["base_kind"] == "hybrid@v1"


def test_world_model_builder_uses_canonical_adapter_when_agi_is_not_requested(monkeypatch):
    monkeypatch.setenv("WORLD_MODEL_KIND", "hybrid@v1")
    model = build_default_world_model()
    description = describe_default_world_model()
    assert isinstance(model, CanonicalDecisionWorldModel)
    assert not isinstance(model, DecisionAGIWorldModel)
    assert description["implementation"] == "bootstrap.canonical_decision_world_model.CanonicalDecisionWorldModel"
    assert description["kind"] == "hybrid@v1"
