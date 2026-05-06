from interfaces.telegram.telegram_action_models import TelegramIncomingMessage
from interfaces.telegram.telegram_handler import TelegramHandler


class _DecisionCore:
    def issue(self, state):
        class _Decision:
            decision_id = 'd1'
            correlation_id = 'c1'
        class _Envelope:
            decision = _Decision()
        self.last_state = state
        return _Envelope()


def test_telegram_handler_can_issue_via_decision_core():
    core = _DecisionCore()
    handler = TelegramHandler(decision_core=core)
    out = handler.handle_message(
        TelegramIncomingMessage(
            chat_id='chat-1',
            user_id='user-1',
            text='hello',
            metadata={'tenant_id': 'tenant-a', 'message_id': 'm-1'},
        )
    )
    assert out.chat_id == 'chat-1'
    assert out.text == 'Decision accepted.'
    assert core.last_state.channel == 'telegram'
    assert core.last_state.message_text == 'hello'
