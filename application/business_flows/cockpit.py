"""Owner cockpit over business-flow projections (port of ClientPlatform native_member_interactions core).

Pure: parse a ``cpm:<screen>[:<page>]`` button, render ``(text, rows)`` from projection
snapshots, normalise navigation (parent Back + Home). Delivery is the executor's job.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from application.business_flows import cockpit_booking as _cb
from application.business_flows import cockpit_events as _ce
from application.business_flows import cockpit_money as _cm
from application.business_flows import cockpit_sales as _cs

PREFIX = "cpm:"
PAGE_SIZE = 6
_ACTION = re.compile(r"[a-z][a-z0-9-]{0,40}")
HOME = ("🏠 Главное меню", "cpm:menu")
_ADD_TIME = ("🕒 Добавить свободное время", "cpm:bk-open")

# screen -> parent screen (donor _NATIVE_PARENT_COMMANDS, limited to screens this port renders)
PARENTS: dict[str, str] = {
    "work": "cpm:menu",
    "today": "cpm:work",
    "bookings": "cpm:work",
    "growth": "cpm:menu",
    "growth-now": "cpm:growth",
    "partners": "cpm:growth",
    "ladder": "cpm:growth",
    "manage": "cpm:menu",
    "messengers": "cpm:manage",
    "connections": "cpm:manage",
    "switch": "cpm:messengers",
    "growth-an": "cpm:growth",
    "money": "cpm:work",
    "services": "cpm:manage",
    "calendar": "cpm:work",
    "customers": "cpm:work",
    "customer": "cpm:customers:0",
    "cust-time": "cpm:customers:0",
    "events": "cpm:work",
    "automation": "cpm:manage",
    "settings": "cpm:manage",
    "team": "cpm:manage",
    "member": "cpm:team:0",
}
PARENTS.update(_cs.PARENTS)
PARENTS.update(_cb.PARENTS)
PARENTS.update(_cm.PARENTS)
PARENTS.update(_ce.PARENTS)


@dataclass(frozen=True)
class Parsed:
    action: str
    args: tuple[str, ...] = ()


@dataclass(frozen=True)
class Snapshot:
    business: str = "Ваш бизнес"
    slots: list[Any] = field(default_factory=list)  # upcoming bookings.Slot
    partners: list[Any] = field(default_factory=list)  # partners.Partner (ranked or insertion order)
    steps: list[Any] = field(default_factory=list)  # ladder.Step
    bots: list[Any] = field(default_factory=list)  # bot_provisioning.Provisioning
    fmt_slot: Any = str
    admin: Any = None  # admin.State
    series: Any = None  # event_series.State
    all_slots: list[Any] = field(default_factory=list)  # every bookings.Slot, past included
    now_ms: int = 0
    money_text: Any = None  # admin.render_summary
    sales: Any = None  # sales.State
    sales_rows: list[Any] = field(default_factory=list)  # [(timestamp_ms, sales_pipeline payload)]
    viewer_id: int = 0  # Telegram user id of the staff member viewing the cockpit
    connections: list[Any] = field(default_factory=list)  # messenger_switching connection rows
    team: dict = field(
        default_factory=dict
    )  # {"roles": {uid: [..]}, "perms": {uid: [..]}} (core.admin.roles_read_model)


def recognizes(data: object) -> bool:
    return isinstance(data, str) and data.startswith(PREFIX)


def parse(data: object) -> Parsed:
    """``cpm:action[:arg...]``; anything malformed becomes the stale screen (never raises)."""
    if not recognizes(data):
        return Parsed("stale")
    parts = str(data)[len(PREFIX) :].split(":")
    if not _ACTION.fullmatch(parts[0]) or len(parts) > 3 or any(len(p) > 40 for p in parts):
        return Parsed("stale")
    return Parsed(parts[0], tuple(parts[1:]))


def page_number(args: tuple[str, ...], *, default: int = 0) -> int:
    if not args:
        return default
    if not args[0].isdigit() or int(args[0]) > 10000:
        raise ValueError("invalid page")
    return int(args[0])


def _rows(*buttons: tuple[str, str]) -> list[list[tuple[str, str]]]:
    return [[(label[:40], cmd)] for label, cmd in buttons]


def _paged(items: list[Any], page: int, screen: str, label) -> tuple[list[str], list[list[tuple[str, str]]], str]:
    count = max(1, -(-len(items) // PAGE_SIZE))
    if page >= count:
        raise ValueError("page outside result set")
    lines = [f"• {label(x)}" for x in items[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]]
    nav = []
    if page > 0:
        nav.append(("◀️ Назад", f"cpm:{screen}:{page - 1}"))
    if page + 1 < count:
        nav.append(("Вперёд ➡️", f"cpm:{screen}:{page + 1}"))
    return lines, ([nav] if nav else []), f"\n\nСтраница {page + 1}/{count}"


def render(parsed: Parsed, snap: Snapshot, *, is_owner: bool) -> tuple[str, list[list[tuple[str, str]]]]:
    if not is_owner:
        return "Для Вашей роли этот раздел недоступен.", []
    try:
        text, rows = _screen(parsed, snap)
    except ValueError:
        text, rows = "Эта кнопка уже неактуальна. Откройте нужный раздел заново.", []
    return text, with_navigation(rows, parsed)


def with_navigation(rows: list[list[tuple[str, str]]], parsed: Parsed) -> list[list[tuple[str, str]]]:
    """Every non-home screen gets a parent-level Back and, when different, Home."""
    if parsed.action == "menu":
        return rows
    parent = PARENTS.get(parsed.action, "cpm:menu")
    nav = [("⬅️ Назад", parent)] + ([HOME] if parent != HOME[1] else [])
    return [r for r in rows if r] + [nav]


def _screen(parsed: Parsed, s: Snapshot) -> tuple[str, list[list[tuple[str, str]]]]:
    a = parsed.action
    if a == "menu":
        return f"🏠 {s.business}\n\nВыберите раздел.", _rows(
            ("📋 Работа", "cpm:work"), ("📈 Рост", "cpm:growth"), ("⚙️ Управление", "cpm:manage")
        )
    if a == "work":
        return "📋 Работа\n\nСегодняшняя сводка и запись клиентов.", _rows(
            ("📊 Что сегодня", "cpm:today"),
            ("📅 Запись", "cpm:bookings:0"),
            ("🗓 Календарь", "cpm:calendar"),
            ("👥 Клиенты", "cpm:customers:0"),
            ("🎤 Встречи и серии", "cpm:events"),
            ("💳 Деньги", "cpm:money"),
            ("💬 Продажи", "cpm:sales"),
        )
    if a == "today":
        booked = [x for x in s.slots if x.status == "booked"]
        nearest = f"\nБлижайшая встреча: {s.fmt_slot(booked[0])}" if booked else ""
        return (
            "📊 Что сегодня происходит\n\n"
            f"Слоты впереди: {len(s.slots)} (занято {len(booked)}){nearest}\n"
            f"Партнёров: {len(s.partners)}\nСтупеней лестницы: {len(s.steps)}"
        ), _rows(("📅 Запись", "cpm:bookings:0"))
    if a == "bookings":
        if not s.slots:
            return "📅 Запись\n\nОткрытого времени нет. Добавьте слот: /add_slot", _rows(_ADD_TIME)
        lines, nav, foot = _paged(s.slots, page_number(parsed.args), "bookings", s.fmt_slot)
        return "📅 Запись\n\n" + "\n".join(lines) + foot, [*_rows(_ADD_TIME), *nav]
    if a == "growth":
        return "📈 Рост\n\nПартнёры и лестница предложений.", _rows(
            ("🧭 Что делать сейчас", "cpm:growth-now"),
            ("🤝 Партнёры", "cpm:partners:0"),
            ("🪜 Лестница предложений", "cpm:ladder"),
            ("📈 Отчёт о росте", "cpm:growth-report"),
            ("📊 Аналитика 7/30 дн.", "cpm:growth-an:7"),
        )
    if a == "partners":
        if not s.partners:
            return "🤝 Партнёры\n\nБаза пуста. Добавьте: /partner_add", []
        lines, nav, foot = _paged(s.partners, page_number(parsed.args), "partners", lambda p: p.name)
        return "🤝 Партнёры\n\n" + "\n".join(lines) + foot, nav
    if a == "ladder":
        body = "\n".join(f"{i}. {x.title}" for i, x in enumerate(s.steps, 1)) or "Ступеней нет. Добавьте: /ladder_add"
        return "🪜 Лестница предложений\n\n" + body, []
    if a == "manage":
        return "⚙️ Управление", _rows(
            ("💬 Мессенджеры", "cpm:messengers"),
            ("🧾 Услуги и цены", "cpm:services"),
            ("🤖 Автоматизация", "cpm:automation"),
            ("🔧 Настройки", "cpm:settings"),
            ("👥 Команда", "cpm:team:0"),
        )
    if a in _cs.PARENTS:
        return _cs.screen(a, parsed.args, s.sales, now_ms=s.now_ms)
    if a in _cb.PARENTS:
        return _cb.screen(a, parsed.args, s.admin, now_ms=s.now_ms)
    if a == "growth-now":
        from application.business_flows import growth_cockpit as gc

        return gc.screen(s)
    if a in _ce.PARENTS:
        return _ce.screen(a, parsed.args, s)
    if a in _cm.PARENTS:
        return _cm.screen(a, parsed.args, s)
    extra = _extra_screen(a, parsed, s)
    if extra is not None:
        return extra
    if a in ("messengers", "connections"):
        return messengers_screen(s)
    if a == "growth-an":
        from application.business_flows import cockpit_growth_analytics as ga

        days = int(parsed.args[0]) if parsed.args and parsed.args[0] in ("7", "30") else 7
        other = "30" if days == 7 else "7"
        return ga.screen(s, period_days=days), _rows((f"📊 За {other} дн.", f"cpm:growth-an:{other}"))
    if a == "switch":
        return switch_screen(parsed, s)
    raise ValueError(a)


_PLATFORM_LABEL = {"telegram": "Telegram", "vk": "VK", "max": "MAX"}


def messengers_screen(s: Snapshot) -> tuple[str, list[list[tuple[str, str]]]]:
    """Connected bots/channels + staff switch buttons (donor messenger_switching, unambiguous targets only)."""
    from application.business_flows import messenger_switching as ms

    body = "\n".join(f"• @{b.username} — {b.status}" for b in s.bots) or "Бот не подключён. Подключить: /connect_bot"
    body += "".join(f"\n• {_PLATFORM_LABEL.get(c['platform'], c['platform'])} — {c['status']}" for c in s.connections)
    platforms = ms.available_switches(bots=s.bots, connections=s.connections) if s.viewer_id > 0 else ()
    rows = [[(f"↪️ Перейти в {_PLATFORM_LABEL[p]}", ms.switch_command(s.viewer_id, p))] for p in platforms]
    return "💬 Мессенджеры\n\n" + body, rows


def switch_screen(parsed: Parsed, s: Snapshot) -> tuple[str, list[list[tuple[str, str]]]]:
    from application.business_flows import messenger_switching as ms

    try:
        dest = ms.switch_destination(":".join(("cpm:switch", *parsed.args)), bots=s.bots, connections=s.connections)
    except ms.MessengerSwitchRejected:
        return "Этот мессенджер сейчас недоступен или подключён неоднозначно.", []
    if dest is None or dest.user_id != s.viewer_id:
        raise ValueError("switch")
    url = ms.public_destination(dest.platform, f"staff{dest.user_id}", bots=s.bots, connections=s.connections)
    return f"↪️ {_PLATFORM_LABEL[dest.platform]}: {url.url if url else dest.public_target}", []


_CONTACT_LABEL = {
    "telegram": "Telegram",
    "vk": "ВКонтакте",
    "max": "MAX",
    "email": "Email",
    "phone": "Телефон",
    "web": "Сайт",
}


def safe_contact(platform: str, *, username: str = "", subject: str = "", display_name: str = "") -> str | None:
    """Donor _safe_contact: a masked contact line; internal profiles and raw phone/email never shown."""
    label = _CONTACT_LABEL.get(str(platform or "").casefold())
    if label is None:
        return None
    if username:
        return f"{label}: " + ("@" + username.lstrip("@") if platform in ("telegram", "vk") else username)
    if platform == "phone" and subject:
        return f"{label}: •••• {subject[-4:]}"
    if platform == "email":
        _, at, dom = subject.partition("@")
        return f"{label}: •••@{dom}" if at and dom else "Email подключён"
    return f"{label}: {display_name}" if display_name else f"{label} подключён"


def customers(slots: list[Any], archived: set[str] = frozenset(), query: str = "") -> list[tuple[str, int]]:
    """Distinct participants with booking counts, most active first (no contact data shown).

    Donor list/search_customers: archived customers are hidden; ``query`` matches the id fragment.
    """
    counts: dict[str, int] = {}
    q = str(query or "").strip()
    for x in slots:
        if x.customer_id and x.customer_id not in archived and q in x.customer_id:
            counts[x.customer_id] = counts.get(x.customer_id, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


_ROLE_RU = {"admin": "администратор", "marketing": "маркетинг"}


def team_screen(a: str, args: tuple[str, ...], team: dict) -> tuple[str, list[list[tuple[str, str]]]]:
    """Read-only team view over admin_role_set/admin_perm_set (donor _team/_members/_member/_permissions)."""
    roles, perms = dict(team.get("roles") or {}), dict(team.get("perms") or {})
    members = sorted(set(roles) | set(perms))
    if a == "member":
        if not args or args[0] not in members:
            raise ValueError("unknown member")
        uid = args[0]
        r = ", ".join(_ROLE_RU.get(x, x) for x in roles.get(uid, [])) or "нет"
        pm = ", ".join(perms.get(uid, [])) or "нет"
        return (
            f"👤 Участник {uid}\n\nРоли: {r}\nПрава: {pm}\n\nИзменить: /role_add {uid} admin|marketing · /role_del {uid} роль · /perm_add · /perm_del",
            [],
        )
    if not members:
        return "👥 Команда\n\nКроме Вас, в команде никого нет. Добавить: /role_add <id> admin|marketing", []
    lines, nav, foot = _paged(
        members,
        page_number(args),
        "team",
        lambda u: f"{u} — " + (", ".join(_ROLE_RU.get(x, x) for x in roles.get(u, [])) or "без ролей"),
    )
    page = page_number(args)
    buttons = [[(f"👤 {u}"[:40], f"cpm:member:{u}")] for u in members[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]]
    return "👥 Команда\n\n" + "\n".join(lines) + foot, [*buttons, *nav]


def _extra_screen(a: str, parsed: Parsed, s: Snapshot) -> tuple[str, list[list[tuple[str, str]]]] | None:
    adm, ser = s.admin, s.series
    if a in ("team", "member"):
        return team_screen(a, parsed.args, s.team)
    if a == "money":
        body = s.money_text(adm) if adm is not None and s.money_text else "Платежей нет."
        return body + "\n\nЗаписать: /pay Услуга | 1500 RUB | номер · Возврат: /refund", _rows(
            ("💳 Все платежи", "cpm:payments:0")
        )
    if a == "services":
        prices = getattr(adm, "prices", {}) or {}
        body = (
            "\n".join(f"• {k} — {v}" for k, v in sorted(prices.items()))
            or "Цен нет. Добавить: /price Услуга | 1500 RUB"
        )
        return "🧾 Услуги и цены\n\n" + body, _rows(("🧾 Цены", "cpm:prices"))
    if a == "settings":
        settings = getattr(adm, "settings", {}) or {}
        body = "\n".join(f"• {k} = {v}" for k, v in sorted(settings.items())) or "Настроек нет."
        return "🔧 Настройки\n\n" + body + "\n\nИзменить: /setting ключ = значение", []
    if a == "automation":
        pending = [x for x in getattr(adm, "approvals", {}).values() if x.status == "pending"]
        auto = "включён" if getattr(adm, "autopilot", False) else "выключен"
        return (
            f"🤖 Автоматизация\n\nАвтопилот: {auto} (/autopilot on|off)\n"
            f"Ждут Вашего решения: {len(pending)} (/approvals)"
        ), []
    if a == "calendar":
        if not s.slots:
            return "🗓 Календарь\n\nВпереди ничего нет. Новая встреча: /new_event Название", []
        days: dict[str, list[str]] = {}
        for x in s.slots:
            label = s.fmt_slot(x)
            days.setdefault(label.split(" ")[0], []).append(label + (" — занято" if x.status == "booked" else ""))
        body = "\n".join(f"{d}\n" + "\n".join(f"  • {v}" for v in vs) for d, vs in days.items())
        return "🗓 Календарь\n\n" + body, []
    if a == "customers":
        arch = getattr(adm, "archived_customers", set()) or set()
        query = next((x for x in parsed.args if not x.isdigit() or len(x) > 4), "")
        people = customers(s.all_slots, arch, query)
        if not people:
            return "👥 Клиенты\n\n" + ("Никого не найдено." if query else "Пока никто не записывался."), []
        page = page_number(tuple(x for x in parsed.args if x != query))
        lines, nav, foot = _paged(people, page, "customers", lambda kv: f"Клиент {kv[0][-6:]} — записей: {kv[1]}")
        start = page * PAGE_SIZE
        open_rows = [
            [(f"Карточка {cid[-6:]}", f"cpm:customer:{cid[:40]}")] for cid, _ in people[start : start + PAGE_SIZE]
        ]
        return "👥 Клиенты\n\n" + "\n".join(lines) + foot, open_rows + nav
    if a == "customer":
        if not parsed.args:
            raise ValueError("customer id")
        cid = parsed.args[0]
        mine = [x for x in s.all_slots if x.customer_id == cid]
        if not mine:
            raise ValueError("unknown customer")
        consent = getattr(ser, "consent", {}).get(cid)
        att = getattr(ser, "attendance", {}) or {}
        rows = [
            f"• {s.fmt_slot(x)} — {att.get((x.slot_id, cid), 'впереди' if x.starts_at_ms > s.now_ms else 'не отмечено')}"
            for x in mine
        ]
        flag = {True: "согласен", False: "отписался"}.get(consent, "не давал")
        from application.business_flows import growth_cockpit as gc

        act = gc.customer_action(s, cid)
        contact = safe_contact("telegram" if cid.isdigit() else "internal")
        head = f"👤 Клиент {cid[-6:]}\n\n" + (f"Контакт: {contact}\n" if contact else "")
        nxt = f"\n\n▶️ Сейчас: {act.title} — {act.reason}" if act else ""
        buttons = [("🕓 История", f"cpm:cust-time:{cid[:40]}")] + ([(f"▶️ {act.title}"[:60], act.cmd)] if act else [])
        return head + f"Согласие на предложения: {flag}\n" + "\n".join(rows) + nxt, _rows(*buttons)
    if a == "cust-time":
        from application.business_flows import customer_timeline as ct

        cid = parsed.args[0] if parsed.args else ""
        from application.business_flows import customer_timeline_sources as cts

        entries = sorted(
            [
                *ct.build(cid, s.all_slots, ser, now_ms=s.now_ms),
                *cts.customer_sales_entries(cid, s.sales_rows, s.sales),
            ],
            key=lambda e: (e.at_ms, e.kind),
        )
        if not entries:
            raise ValueError("unknown customer")
        return f"🕓 История клиента {cid[-6:]}\n\n" + "\n".join(ct.format_lines(entries)), []
    if a == "events":
        days = ", ".join(map(str, getattr(ser, "warmup_days", ()))) or "выключен"
        opted = sum(1 for v in getattr(ser, "consent", {}).values() if v)
        att = getattr(ser, "attendance", {}) or {}
        unmarked = sum(
            1
            for x in s.all_slots
            if x.status == "booked" and x.starts_at_ms <= s.now_ms and (x.slot_id, x.customer_id) not in att
        )
        return (
            f"🎤 Встречи и серии\n\nПрогрев: за {days} дн.\nСогласны на предложения: {opted}\n"
            f"Прошедшие без отметки посещения: {unmarked} (/attendance)\n"
            "Новая встреча: /new_event Название · Тексты: /series"
        ), _rows(("🎤 Отметить посещение", "cpm:ev-conduct"), ("✉️ Тексты прогрева", "cpm:ev-texts"))
    return None


def markup(rows: list[list[tuple[str, str]]]) -> dict[str, Any] | None:
    if not rows:
        return None
    return {"inline_keyboard": [[{"text": t, "callback_data": c} for t, c in row] for row in rows]}
