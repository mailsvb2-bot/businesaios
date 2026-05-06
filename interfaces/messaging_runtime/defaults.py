from __future__ import annotations

from .contracts import ViewModel


def default_compose_view(world_state, message) -> ViewModel:
    reply_text = getattr(world_state, "reply_text", None)
    if reply_text is None and isinstance(world_state, dict):
        reply_text = world_state.get("reply_text")
    if reply_text is None:
        reply_text = "ok"
    return ViewModel(
        channel=message.channel,
        user_id=message.user_id,
        correlation_id=message.correlation_id,
        body=str(reply_text),
        metadata={"source": "multichannel_runtime"},
    )
