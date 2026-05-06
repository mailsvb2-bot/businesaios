from runtime.messaging.router import UnifiedConversationRouter


def test_router_normalizes_without_business_logic():
    router = UnifiedConversationRouter()
    msg = router.normalize(
        channel="web",
        tenant_id="tenant-a",
        payload={"session_id": "s-1", "text": "hello", "client_message_id": "m-1", "locale": "en"},
    )
    assert msg.channel == "web_chat"
    assert msg.tenant_id == "tenant-a"
    assert msg.user_id == "s-1"
    assert msg.text == "hello"
    assert msg.transport_message_id == "m-1"
    assert msg.metadata["locale"] == "en"
