from __future__ import annotations

from bootstrap.canonical_decision_world_model import CanonicalDecisionWorldModel
from bootstrap.decision_agi_world_model import DecisionAGIWorldModel


def test_decision_agi_world_model_extends_canonical_adapter() -> None:
    assert issubclass(DecisionAGIWorldModel, CanonicalDecisionWorldModel)
