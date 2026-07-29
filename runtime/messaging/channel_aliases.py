from __future__ import annotations

# All accepted spellings terminate in the canonical names declared by
# ``runtime.messaging.channel_types``. No interface layer may reverse this map.
ALIASES = {
    "tg": "telegram",
    "wa": "whatsapp",
    "web": "web_chat",
    "webchat": "web_chat",
    "widget": "web_chat",
    "wc": "web_chat",
    "api_gateway": "api",
    "instagram_dm": "instagram",
    "ig": "instagram",
    "fb": "messenger",
    "facebook_messenger": "messenger",
}

__all__ = ["ALIASES"]
