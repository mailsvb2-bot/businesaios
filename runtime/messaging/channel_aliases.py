from __future__ import annotations

# All accepted spellings terminate in the canonical names declared by
# ``runtime.messaging.channel_types``. No ingress or interface layer may keep a
# reverse/parallel alias table.
ALIASES = {
    "tg": "telegram",
    "telegram_bot": "telegram",
    "wa": "whatsapp",
    "whats_app": "whatsapp",
    "vkontakte": "vk",
    "vk_bot": "vk",
    "max_bot": "max",
    "max_messenger": "max",
    "mail": "email",
    "e_mail": "email",
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
