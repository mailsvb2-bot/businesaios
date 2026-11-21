from __future__ import annotations

from interfaces.messaging._shared.provider_surface import make_build_config

build_config = make_build_config(provider="web_chat", env_prefix="WEB_CHAT", default_mode="configured_noop")


WEB_CHAT_NOOP_LABEL = "Веб-чат не подключён — доставка отключена"


def web_chat_delivery_status() -> dict[str, object]:
    """Read-only state of the existing web-chat runner; never claim delivery."""
    cfg = build_config()
    mode = str(cfg.mode)
    enabled = mode != "configured_noop" and bool(cfg.endpoint)
    return {"channel": "web_chat", "mode": mode, "delivery_enabled": enabled,
            "label": "Веб-чат настроен; доставка требует квитанции" if enabled else WEB_CHAT_NOOP_LABEL}
