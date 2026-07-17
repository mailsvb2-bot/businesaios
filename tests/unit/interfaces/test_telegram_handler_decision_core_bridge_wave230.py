from __future__ import annotations

import pytest

from core.ai import (
    _reset_decision_core_singleton_for_tests,
    set_decision_core_singleton,
)
from interfaces.telegram.telegram_action_models import TelegramIncomingMessage
from interfaces.telegram.telegram_handler import TelegramHandler


@pytest.fixture(autouse=True)
def _isolated_decision_core_singleton():
    _reset_decision_core_singleton_for_tests()
    try:
        yield
    finally:
        _reset_decision_core_singleton_for_tests()


class _DecisionCore:
    def issue(self, state):
        class _Decision:
            decision_id = "d1"
            correlation_id = "c1"

        class _Envelope:
            decision = _Decision()

        self.last_state = state
        return _Envelope()


def test_telegram_handler_can_issue_via_registered_decision_core() -> None:
    core = _DecisionCore()
    set_decision_core_singleton(core)
    handler = TelegramHandler(decision_core=core)

    out = handler.handle_message(
        TelegramIncomingMessage(
            chat_id="chat-1",
            user_id="user-1",
            text="hello",
            metadata={"tenant_id": "tenant-a", "message_id": "m-1"},
        )
    )

    assert out.chat_id == "chat-1"
    assert out.text == "Decision accepted."
    assert core.last_state.channel == "telegram"
    assert core.last_state.message_text == "hello"
