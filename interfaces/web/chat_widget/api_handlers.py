
from __future__ import annotations

from interfaces.web.chat_widget.widget_inbound_normalizer import normalize_widget_inbound
from runtime.messaging.inbound_owner_lock import assert_inbound_owner
from runtime.messaging.inbound_to_world_state import map_inbound_to_world_state
from runtime.messaging.router import UnifiedConversationRouter


class WebChatAPIHandlers:
    def __init__(self, *, router: UnifiedConversationRouter | None = None):
        self._router = router or UnifiedConversationRouter()

    def ingest_message(self, payload, *, tenant_id: str = "default") -> dict:
        assert_inbound_owner('interfaces.web.chat_widget.api_handlers')
        normalized = normalize_widget_inbound(payload)
        msg = self._router.normalize(channel="web_chat", payload=normalized, tenant_id=tenant_id)
        world_state_input = map_inbound_to_world_state(msg)
        return {
            "tenant_id": msg.tenant_id,
            "user_id": msg.user_id,
            "channel": msg.channel,
            "text": msg.text,
            "correlation_id": msg.correlation_id,
            "transport_message_id": msg.transport_message_id,
            "world_state_input": {
                "tenant_id": world_state_input.tenant_id,
                "user_id": world_state_input.user_id,
                "channel": world_state_input.channel,
                "message_text": world_state_input.message_text,
                "correlation_id": world_state_input.correlation_id,
                "transport_message_id": world_state_input.transport_message_id,
            },
        }
