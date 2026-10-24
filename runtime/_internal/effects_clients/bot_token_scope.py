"""Delivery-token scope: replies to a customer bot's chat go out with that bot's token.

The gateway resolves the token from the vault ref and enters the scope around one decision; the
canonical sendMessage path reads it. Never logged; financial (Stars) calls ignore the scope."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_SCOPE: ContextVar[str] = ContextVar("customer_bot_token_scope", default="")


@contextmanager
def customer_bot_token_scope(token: str) -> Iterator[None]:
    value = str(token or "").strip()
    if not value:
        raise ValueError("customer_bot_token_required")
    reset = _SCOPE.set(value)
    try:
        yield
    finally:
        _SCOPE.reset(reset)


def scoped_bot_token() -> str:
    return _SCOPE.get()


def scope_tag() -> str:
    """Non-secret discriminator for delivery keys (same chat_id differs per bot)."""
    token = _SCOPE.get()
    return "bot:" + hashlib.sha256(token.encode()).hexdigest()[:12] if token else ""


__all__ = ["customer_bot_token_scope", "scope_tag", "scoped_bot_token"]
