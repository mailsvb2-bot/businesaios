from __future__ import annotations

from interfaces.web.settings.messaging_preferences.page_presenter import MessagingPreferencesPageModel


def page_to_dict(model: MessagingPreferencesPageModel) -> dict:
    return {
        "setting_key": model.setting_key,
        "primary": model.primary,
        "enabled": list(model.enabled),
        "verified": list(model.verified),
        "groups": [
            {
                "key": group.key,
                "title": group.title,
                "items": [
                    {
                        "key": item.key,
                        "label": item.label,
                        "family": item.family,
                        "tier": item.tier,
                        "description": item.description,
                        "enabled": item.enabled,
                        "primary": item.primary,
                        "verified": item.verified,
                    }
                    for item in group.items
                ],
            }
            for group in model.groups
        ],
    }
