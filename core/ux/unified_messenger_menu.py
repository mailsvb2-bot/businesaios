"""One ClientPlatform-branded navigation contract across existing messaging providers.

Presentation only. All actions use existing BusinessAIOS callback owners or a
transparent informational route; no donor runtime, second decision owner or sender.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.ux.callbacks import (
    CB_ADMIN_MENU, CB_ADS_APPLY_MENU, CB_AUTOPILOT_MENU, CB_GROWTH_MENU,
    CB_MENU_MAIN, CB_SETTINGS_MENU, CB_SETTINGS_STATE, CB_SUB_MENU,
)

BRAND = "ClientPlatform"

SECTION_PREFIX = "cp:section:"


@dataclass(frozen=True)
class NavigationItem:
    key: str
    label: str
    callback: str
    roles: frozenset[str]


_ITEMS = (
    NavigationItem("customers", "💬 Клиенты и обращения", SECTION_PREFIX + "customers", frozenset({"owner", "admin", "operator"})),
    NavigationItem("sales", "💰 Продажи", SECTION_PREFIX + "sales", frozenset({"owner", "admin", "operator", "marketer"})),
    NavigationItem("marketing", "📣 Реклама и продвижение", CB_GROWTH_MENU, frozenset({"owner", "admin", "marketer"})),
    NavigationItem("ai", "🤖 ИИ и автопилот", CB_AUTOPILOT_MENU, frozenset({"owner", "admin", "operator", "marketer"})),
    NavigationItem("ads_apply", "🧩 Ads Apply (prod)", CB_ADS_APPLY_MENU, frozenset({"marketer", "operator"})),
    NavigationItem("results", "📊 Результаты", CB_SETTINGS_STATE, frozenset({"owner", "admin", "operator", "marketer"})),
    NavigationItem("payments", "💳 Оплаты и тарифы", CB_SUB_MENU, frozenset({"owner", "admin"})),
    NavigationItem("settings", "⚙️ Настройки", CB_SETTINGS_MENU, frozenset({"owner", "admin"})),
    NavigationItem("administration", "🛠 Администрирование", CB_ADMIN_MENU, frozenset({"admin"})),
)


def menu_items(*, role: str, is_admin: bool = False) -> tuple[NavigationItem, ...]:
    normalized = str(role or "").strip().lower()
    if normalized not in {"owner", "admin", "operator", "marketer"}:
        normalized = "operator"
    roles = {normalized}
    if is_admin:
        roles.add("admin")
    return tuple(item for item in _ITEMS if item.roles.intersection(roles))


def menu_text(*, role: str, is_admin: bool = False) -> str:
    labels = "\n".join(f"{index}. {item.label}" for index, item in enumerate(menu_items(role=role, is_admin=is_admin), 1))
    return f"🏠 {BRAND}\n\nУправление вашим бизнесом в одном месте.\n\n{labels}\n\nВыберите раздел:"


def telegram_menu(*, role: str, is_admin: bool = False) -> dict:
    rows = [[{"text": item.label, "callback_data": item.callback}]
            for item in menu_items(role=role, is_admin=is_admin)]
    return {"inline_keyboard": rows}


def plain_channel_menu(*, channel: str, role: str, is_admin: bool = False) -> dict:
    """Provider-neutral UI, safe for VK/MAX without claiming unsupported buttons.

    Native button serialization is performed only by existing provider egress.
    Text is the baseline for every registered messaging channel. Native callback\n    transport remains the responsibility of the existing provider egress.
    """
    from application.business_autonomy.provider_catalog import MESSAGING_CHANNEL_PROVIDER_KEYS

    if channel not in MESSAGING_CHANNEL_PROVIDER_KEYS:
        raise ValueError("unsupported_clientplatform_channel")
    return {"channel": channel, "text": menu_text(role=role, is_admin=is_admin),
            "actions": tuple({"key": x.key, "label": x.label, "callback": x.callback}
                             for x in menu_items(role=role, is_admin=is_admin))}


def section_text(callback: str) -> str | None:
    return None  # obsolete information-only route; navigation uses canonical owners


def back_button() -> dict:
    return {"inline_keyboard": [[{"text": "⬅️ Главное меню", "callback_data": CB_MENU_MAIN}]]}
