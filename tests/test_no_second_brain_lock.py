from __future__ import annotations

import inspect

from core.ai.decision_core import DecisionCore


def test_llm_layer_is_not_decision_core() -> None:
    try:
        from core.ai.message_generator import MessageGenerator  # type: ignore
    except Exception:
        return

    src = inspect.getsource(MessageGenerator)
    forbidden = ["def decide", "def choose_action", "DecisionCore("]
    for tok in forbidden:
        assert tok not in src


def test_decision_core_has_decide() -> None:
    assert hasattr(DecisionCore, "decide")
