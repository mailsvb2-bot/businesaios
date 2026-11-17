"""One ClientPlatform-branded navigation contract across existing messaging providers.

Presentation only. All actions use existing BusinessAIOS callback owners or a
transparent informational route; no donor runtime, second decision owner or sender.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from core.ux.callbacks import CB_ADMIN_MENU, CB_ADS_APPLY_MENU, CB_AUTOPILOT_MENU, CB_MENU_MAIN, CB_SETTINGS_MENU

BRAND = "ClientPlatform"
BUSINESS_ONBOARDING_URL = "https://app.businessaios.ru/"

SECTION_PREFIX = "cp:section:"


@dataclass(frozen=True)
class NavigationItem:
    key: str
    label: str
    callback: str
    roles: frozenset[str]


_ITEMS = (
    NavigationItem("connect", "➕ Подключить мой бизнес", SECTION_PREFIX + "connect", frozenset({"owner", "admin", "operator", "marketer"})),
    NavigationItem("customers", "💬 Клиенты и обращения", SECTION_PREFIX + "customers", frozenset({"owner", "admin", "operator"})),
    NavigationItem("sales", "💰 Продажи", SECTION_PREFIX + "sales", frozenset({"owner", "admin", "operator", "marketer"})),
    NavigationItem("marketing", "📣 Реклама и продвижение", "cpm:growth", frozenset({"owner", "admin", "marketer"})),
    NavigationItem("ai", "🤖 ИИ и автопилот", CB_AUTOPILOT_MENU, frozenset({"owner", "admin", "operator", "marketer"})),
    NavigationItem("ads_apply", "🧩 Ads Apply (prod)", CB_ADS_APPLY_MENU, frozenset({"marketer", "operator"})),
    NavigationItem("results", "📊 Результаты", "cpm:growth-an:7", frozenset({"owner", "admin", "operator", "marketer"})),
    NavigationItem("payments", "💳 Оплаты и тарифы", "cpm:money", frozenset({"owner", "admin"})),
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
    return tuple(item for item in _ITEMS if item.roles.intersection(roles)
                 and (is_admin or item.key not in {"customers", "sales", "marketing", "results", "payments"}))


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


DEFAULT_ONBOARDING_URL = BUSINESS_ONBOARDING_URL


def validated_onboarding_url(raw: str) -> str:
    """Constrain operator's public HTTPS destination; never forward identifiers."""
    value = str(raw or "").strip()
    if not value:
        return DEFAULT_ONBOARDING_URL
    if len(value) > 200 or any(c.isspace() for c in value):
        return DEFAULT_ONBOARDING_URL
    try:
        parts = urlsplit(value)
        if (parts.scheme != "https" or not parts.hostname or parts.username is not None
                or parts.password is not None or parts.query or parts.fragment
                or parts.port is not None):
            return DEFAULT_ONBOARDING_URL
        if not parts.hostname.replace(".", "").replace("-", "").isalnum():
            return DEFAULT_ONBOARDING_URL
    except ValueError:
        return DEFAULT_ONBOARDING_URL
    return value


def connect_business_view(*, onboarding_url: str, bound_business_id: str,
                          show_binding: bool = False) -> tuple[str, dict]:
    """Canonical web onboarding handoff, never Telegram-side registration."""
    url = validated_onboarding_url(onboarding_url)
    message = (
        f"➕ Подключение бизнеса\n\n"
        f"Подключение выполняется в веб-кабинете {BRAND}.\n"
        "1. Войдите в кабинет.\n"
        "2. Создайте бизнес или выберите существующий.\n"
        "3. Подтвердите выбор бизнеса в кабинете.\n\n"
        "Личные данные Telegram через эту ссылку не передаются."
    )
    if show_binding:
        message += f"\n\nПривязанный бизнес: {bound_business_id or 'не выбран'}."
    return message, {"inline_keyboard": [
        [{"text": "🌐 Открыть веб-кабинет", "url": url}],
        [{"text": "⬅️ Главное меню", "callback_data": CB_MENU_MAIN}],
    ]}


def section_text(callback: str) -> str | None:
    return None  # obsolete information-only route; navigation uses canonical owners


def back_button() -> dict:
    return {"inline_keyboard": [[{"text": "⬅️ Главное меню", "callback_data": CB_MENU_MAIN}]]}
