from __future__ import annotations

from runtime.messaging.adapter_protocol import MessageAdapter


def test_message_adapter_protocol_runtime_surface_is_non_executing() -> None:
    assert MessageAdapter.send(object(), object()) is None
