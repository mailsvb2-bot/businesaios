import pytest

from runtime.enforcement.action_contracts import validate_telegram_transport_payload


def test_non_telegram_send_message_is_not_forced_to_numeric_chat_id():
    validate_telegram_transport_payload(
        action="send_message@v1",
        payload={"user_id": "wa:15551230000", "text": "hi", "channel": "whatsapp"},
        run_mode="telegram",
    )


def test_telegram_send_message_still_requires_numeric_chat_id():
    with pytest.raises(RuntimeError, match="TELEGRAM_CHAT_ID_REQUIRED"):
        validate_telegram_transport_payload(
            action="send_message@v1",
            payload={"user_id": "not_numeric", "text": "hi", "channel": "telegram"},
            run_mode="telegram",
        )
