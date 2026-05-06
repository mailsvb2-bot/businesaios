from __future__ import annotations


def page_to_dict(model) -> dict:
    return {
        "setting_key": model.setting_key,
        "items": [
            {
                "recipient_user_id": item.recipient_user_id,
                "channel": item.channel,
                "min_level": item.min_level,
                "enabled": item.enabled,
                "code_filters": list(item.code_filters),
                "user_scope": list(item.user_scope),
            }
            for item in model.items
        ],
        "channels": [
            {"key": item.key, "label": item.label}
            for item in model.channels
        ],
        "levels": [
            {"key": item.key, "label": item.label}
            for item in model.levels
        ],
    }
