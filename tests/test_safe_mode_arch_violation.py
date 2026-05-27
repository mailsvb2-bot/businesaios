from __future__ import annotations

import importlib


def test_multi_decisioncore_triggers_safe_mode_and_exit():
    ai = importlib.import_module("core.ai")
    DecisionCore = importlib.import_module("core.ai.decision_core").DecisionCore

    # Create two different dummy cores (bypass actual init using object.__new__)
    c1 = object.__new__(DecisionCore)
    c2 = object.__new__(DecisionCore)

    ai.set_decision_core_singleton(c1)
    try:
        ai.set_decision_core_singleton(c2)
        assert False, "Expected SystemExit on MULTI_DECISIONCORE"
    except SystemExit as e:
        assert "MULTI_DECISIONCORE" in str(e)

    sm = importlib.import_module("core.runtime.safe_mode")
    assert sm.is_safe_mode()
