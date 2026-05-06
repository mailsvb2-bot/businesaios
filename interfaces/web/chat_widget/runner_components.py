from __future__ import annotations

from interfaces.messaging._shared.provider_surface import make_build_config


build_config = make_build_config(provider="web_chat", env_prefix="WEB_CHAT", default_mode="configured_noop")
