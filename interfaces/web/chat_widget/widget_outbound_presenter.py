from __future__ import annotations


def present_widget_message(*, text: str, external_id: str, mode: str) -> dict:
    return {
        "ok": True,
        "channel": "web_chat",
        "mode": str(mode),
        "external_id": str(external_id),
        "message": str(text),
    }
