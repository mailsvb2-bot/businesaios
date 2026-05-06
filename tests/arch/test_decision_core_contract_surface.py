from __future__ import annotations

from core.ai.decision_core import DecisionCore as SovereignDecisionCore
from core.decision_core import DecisionCore as PublicDecisionCore
from core.decision_core_contract import CANONICAL_DECISION_CORE_IMPORT_PATH


def test_public_and_sovereign_surfaces_resolve_to_one_real_decision_core() -> None:
    assert PublicDecisionCore is SovereignDecisionCore
    assert SovereignDecisionCore.CANONICAL_IMPORT_PATH == CANONICAL_DECISION_CORE_IMPORT_PATH
    assert SovereignDecisionCore.IS_SOVEREIGN_DECISION_CORE is True
