"""Sealed server helpers for runtime effects."""

from __future__ import annotations

from typing import Any

from .effects_clients.yookassa_webhook_server import (
    start_yookassa_webhook_server_in_thread as _start_yookassa_webhook_server_in_thread,
)
from .servers.health_server import start_health_server_in_thread


def start_yookassa_webhook_server_in_thread(*, host: str, port: int, path: str, event_store: Any, payment_outbox: Any) -> Any:
    return _start_yookassa_webhook_server_in_thread(
        host=str(host),
        port=int(port),
        path=str(path),
        event_store=event_store,
        payment_outbox=payment_outbox,
    )
__all__ = [
    "start_health_server_in_thread",
    "start_yookassa_webhook_server_in_thread",
]
