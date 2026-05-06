from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from runtime.messaging.channel_normalizer import normalize_channel
from runtime.messaging.channel_preference import ChannelPreference
from runtime.messaging.settings import SETTING_KEY


@dataclass(frozen=True)
class OptionViewModel:
    key: str
    label: str
    family: str
    tier: str
    description: str
    enabled: bool
    primary: bool
    verified: bool


@dataclass(frozen=True)
class GroupBucket:
    key: str
    title: str
    items: tuple[OptionViewModel, ...]


@dataclass(frozen=True)
class MessagingPreferencesPageModel:
    setting_key: str
    primary: str
    enabled: tuple[str, ...]
    verified: tuple[str, ...]
    groups: tuple[GroupBucket, ...]


_TITLES = {
    "tier_1": "Tier 1",
    "tier_2": "Tier 2",
    "tier_3": "Tier 3",
}

_OPTIONS = (
    ("telegram", "Telegram", "messaging", "tier_1", "Telegram bot interface"),
    ("whatsapp", "WhatsApp", "messaging", "tier_1", "WhatsApp business messaging"),
    ("sms", "SMS", "messaging", "tier_1", "SMS business messaging"),
    ("email", "Email", "messaging", "tier_1", "Email communication"),
    ("instagram", "Instagram DM", "messaging", "tier_2", "Instagram direct messages"),
    ("messenger", "Facebook Messenger", "messaging", "tier_2", "Facebook Messenger channel"),
    ("webchat", "Website Chat", "web", "tier_2", "Embedded website chat widget (alias: web_chat)"),
    ("api_gateway", "API", "web", "tier_2", "Direct API-driven messaging (alias: api)"),
    ("line", "LINE", "regional", "tier_3", "LINE regional channel"),
    ("wechat", "WeChat", "regional", "tier_3", "WeChat regional channel"),
    ("kakaotalk", "KakaoTalk", "regional", "tier_3", "KakaoTalk regional channel"),
    ("viber", "Viber", "regional", "tier_3", "Viber regional channel"),
)


def _read_verified_channels(value: Any) -> tuple[str, ...]:
    if isinstance(value, dict):
        raw = value.get("verified") or ()
    elif isinstance(value, (list, tuple, set)):
        raw = value
    else:
        raw = ()

    out: list[str] = []
    for item in raw:
        text = str(item or "").strip()
        if not text:
            continue
        try:
            out.append(normalize_channel(text))
        except ValueError:
            continue
    return tuple(dict.fromkeys(out))


def _read_existing_preference(value: Any) -> ChannelPreference:
    if isinstance(value, dict):
        pref = ChannelPreference.from_mapping(value)
        return ChannelPreference(
            primary=pref.primary,
            enabled=pref.enabled,
            verified=_read_verified_channels(value),
        )
    return ChannelPreference(primary="telegram", enabled=("telegram",), verified=())


def _build_groups(items: tuple[OptionViewModel, ...]) -> tuple[GroupBucket, ...]:
    buckets: dict[str, list[OptionViewModel]] = defaultdict(list)
    for item in items:
        buckets[item.tier].append(item)

    return tuple(
        GroupBucket(key=key, title=_TITLES[key], items=tuple(buckets.get(key, ())))
        for key in ("tier_1", "tier_2", "tier_3")
    )


def present_page(existing_value) -> MessagingPreferencesPageModel:
    preference = _read_existing_preference(existing_value)
    items = tuple(
        OptionViewModel(
            key=key,
            label=label,
            family=family,
            tier=tier,
            description=description,
            enabled=key in preference.enabled,
            primary=key == preference.primary,
            verified=key in preference.verified,
        )
        for key, label, family, tier, description in _OPTIONS
    )
    return MessagingPreferencesPageModel(
        setting_key=SETTING_KEY,
        primary=preference.primary,
        enabled=preference.enabled,
        verified=preference.verified,
        groups=_build_groups(items),
    )
