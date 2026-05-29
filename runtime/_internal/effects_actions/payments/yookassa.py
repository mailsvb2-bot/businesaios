from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Tuple

from runtime._internal.effect_types import EffectActionType
from runtime._internal.effects_clients.yookassa_webhook_server import (
    start_yookassa_webhook_server_in_thread as _start_yookassa_webhook_server_in_thread,
)
from runtime._internal.router_support import execute_effect_action_sync


def yookassa_create_payment(*, effects: Any | None = None, decision_id: str, amount: int, currency: str, user_id: str, metadata: dict[str, Any] | None = None) -> tuple[bool, dict[str, Any]]:
    from core.payments.provider import idempotence_key_for_order
    cur = str(currency or "RUB").upper().strip() or "RUB"
    if cur != "RUB": return False, {"error": "UNSUPPORTED_CURRENCY", "currency": cur}
    md = metadata if isinstance(metadata, dict) else {}
    out = execute_effect_action_sync(effects, EffectActionType.PAYMENTS_YOOKASSA_CREATE, {
        "amount_rub": (Decimal(int(amount)) / Decimal("100")).quantize(Decimal("0.01")),
        "description": str((md or {}).get("description") or "Payment").strip() or "Payment",
        "customer_id": str(user_id or ""),
        "idempotence_key": idempotence_key_for_order(str((md or {}).get("order_id") or decision_id).strip() or str(decision_id)),
        "metadata": dict(md or {}),
    })
    return bool(out.get("ok", False)), dict(out)

def yookassa_get_payment_status(*, effects: Any | None = None, external_payment_id: str) -> str:
    return str(execute_effect_action_sync(effects, EffectActionType.PAYMENTS_YOOKASSA_GET_STATUS, {"external_payment_id": str(external_payment_id), "timeout_s": 20}).get("status") or "unknown")

def start_webhook_server(*, host: str, port: int, path: str, event_store: Any, payment_outbox: Any) -> Any:
    return _start_yookassa_webhook_server_in_thread(host=host, port=port, path=path, event_store=event_store, payment_outbox=payment_outbox)
