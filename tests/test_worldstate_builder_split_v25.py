from interfaces.telegram.parsing.telegram_context import TelegramContext
from interfaces.telegram.runtime.worldstate_causal import build_causal_evidence_from_event_window
from interfaces.telegram.runtime.worldstate_overlays import build_overlays_from_context


def test_worldstate_helpers_are_deterministic_for_empty_window():
    ctx = TelegramContext(update_id=1, chat_id="42", message_id=None, text="hi", command=None, args="", is_callback=False, callback_data=None, callback_query_id=None, raw={})
    overlays = build_overlays_from_context(ctx=ctx, tenant_id="tenant-a", now_ms=123)
    assert overlays.user_id == "42"
    assert build_causal_evidence_from_event_window([]) == {}
