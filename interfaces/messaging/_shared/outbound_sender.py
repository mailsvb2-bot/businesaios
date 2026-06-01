from __future__ import annotations

from interfaces.messaging._shared.provider_config import ProviderConfig
from runtime.messaging.outbound_message import OutboundMessage

NOOP_MODE = "configured_noop"


def _noop_result(*, cfg: ProviderConfig, msg: OutboundMessage) -> dict:
    return {
        "ok": True,
        "accepted": False,
        "mode": NOOP_MODE,
        "provider": cfg.provider,
        "external_id": "",
        "reason": "provider_not_enabled",
        "delivery_key": msg.delivery_key,
        "delivered": False,
        "noop": True,
        "execution_state": "not_sent",
        "delivery_disposition": "suppressed",
        "observability_hint": "configured_noop: provider wiring is disabled; treat as unsent in delivery metrics",
    }


def _sent_result(*, cfg: ProviderConfig, msg: OutboundMessage) -> dict:
    return {
        "ok": True,
        "accepted": True,
        "mode": cfg.mode,
        "provider": cfg.provider,
        "external_id": msg.delivery_key,
        "endpoint": cfg.endpoint,
        "sender": cfg.sender,
        "delivery_key": msg.delivery_key,
        "text_preview": str(msg.text or "")[:120],
        "delivered": True,
        "noop": False,
        "execution_state": "sent",
        "delivery_disposition": "delivered",
    }


def send_outbound(*, cfg: ProviderConfig, msg: OutboundMessage) -> dict:
    if cfg.mode == NOOP_MODE:
        return _noop_result(cfg=cfg, msg=msg)
    return _sent_result(cfg=cfg, msg=msg)
