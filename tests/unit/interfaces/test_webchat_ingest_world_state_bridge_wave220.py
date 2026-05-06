from interfaces.web.chat_widget.api_handlers import WebChatAPIHandlers


def test_webchat_ingest_exposes_world_state_input():
    api = WebChatAPIHandlers()
    out = api.ingest_message(
        {"session_id": "s1", "text": "hello", "client_message_id": "m1"},
        tenant_id="t1",
    )
    assert out["world_state_input"]["tenant_id"] == "t1"
    assert out["world_state_input"]["message_text"] == "hello"
