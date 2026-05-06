"""Telegram-specific effects protocol mixin.

Extracted from EffectsPort (Patch 05) to reduce class surface.
"""

from __future__ import annotations
from typing import Any, Protocol


class EffectsTelegramMixin(Protocol):
    """Telegram side-effect methods."""

    def send_telegram_message(self, *, chat_id: str, text: str, **kw: Any) -> Any: ...
    def edit_telegram_message(self, *, chat_id: str, message_id: int, text: str, **kw: Any) -> Any: ...
    def answer_callback_query(self, *, callback_query_id: str, text: str, **kw: Any) -> Any: ...
    def send_telegram_photo(self, *, chat_id: str, photo: str, caption: str, **kw: Any) -> Any: ...
    def send_telegram_invoice(self, **kw: Any) -> Any: ...
