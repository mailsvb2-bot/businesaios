"""One ClientPlatform-branded navigation contract across existing messaging providers.

Presentation only. All actions use existing BusinessAIOS callback owners or a
transparent informational route; no donor runtime, second decision owner or sender.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from core.ux.callbacks import CB_ADMIN_MENU, CB_ADS_APPLY_MENU, CB_AUTOPILOT_MENU, CB_MENU_MAIN, CB_SETTINGS_MENU

BRAND = "ClientPlatform"
BUSINESS_ONBOARDING_URL = "https://app.businessaios.ru/"

SECTION_PREFIX = "cp:section:"


@dataclass(frozen=True)
class NavigationItem:
    key: str
    label: str
    callback: str
    permission: str


_ITEMS = (
    NavigationItem("connect", "➕ Подключить мой бизнес", SECTION_PREFIX + "connect", "connect"),
    NavigationItem("customers", "💬 Клиенты и обращения", SECTION_PREFIX + "customers", "customers"),
    NavigationItem("sales", "💰 Продажи", SECTION_PREFIX + "sales", "sales"),
    NavigationItem("partners", "🤝 Партнёры", SECTION_PREFIX + "partners", "business_manage"),
    NavigationItem("marketing", "📣 Реклама и продвижение", "cpm:growth", "marketing"),
    NavigationItem("ai", "🤖 ИИ-директор и автопилот", CB_AUTOPILOT_MENU, "autopilot"),
    NavigationItem("ads_apply", "🧩 Ads Apply (prod)", CB_ADS_APPLY_MENU, "ads_apply"),
    NavigationItem("results", "📊 Результаты", "cpm:growth-an:7", "analytics"),
    NavigationItem("payments", "💳 Оплаты и тарифы", "cpm:money", "payments"),
    NavigationItem("settings", "⚙️ Настройки", CB_SETTINGS_MENU, "business_manage"),
    NavigationItem("administration", "🛠 Администрирование", CB_ADMIN_MENU, "administration"),
)


def menu_items(*, role: str, is_admin: bool = False) -> tuple[NavigationItem, ...]:
    from core.users.roles import ROLE_PERMISSIONS, permissions_for

    role = str(role or "").strip().lower()
    if role not in ROLE_PERMISSIONS:
        role = "guest"
    permissions = permissions_for(is_platform_admin=is_admin, roles=(role,))
    return tuple(item for item in _ITEMS if item.permission in permissions and not
                 ((is_admin or role in {"admin", "platform_admin"}) and item.key == "ads_apply"))


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
    actions = tuple({"key": x.key, "label": x.label, "callback": x.callback}
                    for x in menu_items(role=role, is_admin=is_admin))
    # P1-24: the same actions as the canonical inline keyboard; the existing VK/MAX
    # egress (provider_payload_normalizers) turns it into native buttons and the
    # inbound decoder returns the pressed callback as text. The numbered text
    return {"channel": channel, "text": menu_text(role=role, is_admin=is_admin), "actions": actions,
            "reply_markup": {"inline_keyboard": [  # 2 per row: fits VK inline (≤6 rows, ≤10) and MAX
                [{"text": a["label"], "callback_data": a["callback"]} for a in actions[i:i + 2]]
                for i in range(0, len(actions), 2)]}}


DEFAULT_ONBOARDING_URL = BUSINESS_ONBOARDING_URL


def validated_onboarding_url(raw: str) -> str:
    """Constrain operator's public HTTPS destination; never forward identifiers."""
    value = str(raw or "")
    # Pure HTTPS DNS validation; the presentation core never imports transports.
    if (value != value.strip() or len(value) > 200 or any(c.isspace() for c in value)
            or not value.startswith("https://")):
        return DEFAULT_ONBOARDING_URL
    host, sep, path = value[8:].partition("/")
    labels = host.split(".")
    if not 1 <= len(labels) <= 20 or any(
        not 1 <= len(label) <= 63 or
        re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", label) is None
        for label in labels):
        return DEFAULT_ONBOARDING_URL
    if sep and re.fullmatch(r"[A-Za-z0-9._~!$&'()*+,;=:@%/-]*", path) is None:
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
