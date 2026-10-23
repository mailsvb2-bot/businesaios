"""Business catalog: directions, offerings and formats (port of clientplatform native
direction/offering/format screens over ``business_admin@v1`` facts).

Archive never deletes: archived directions/offerings keep history and can be restored
(directions) — mirrors donor ``archive_activity_direction`` / ``archive_business_offering``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from application.business_flows.projection import stable_id

FORMATS = {
    "individual": "индивидуально",
    "group": "группа",
    "event": "мероприятие",
    "online": "онлайн",
    "course": "курс",
}
DEFAULT_ON = frozenset({"individual", "group", "event"})


@dataclass
class Direction:
    direction_id: str
    title: str
    description: str
    goal: str = ""
    archived: bool = False


@dataclass
class Offering:
    offering_id: str
    fmt: str
    title: str
    description: str
    direction_id: str | None
    archived: bool = False


@dataclass
class Catalog:
    directions: dict[str, Direction] = field(default_factory=dict)
    offerings: dict[str, Offering] = field(default_factory=dict)
    formats: set[str] = field(default_factory=lambda: set(DEFAULT_ON))
    activity: str = ""
    timezone: str = "Europe/Moscow"
    details: dict[str, Any] = field(default_factory=dict)
    details_confirmed: bool = False


def replay(payloads: list[dict[str, Any]]) -> Catalog:
    c = Catalog()
    for p in payloads:
        s = p.get("step")
        if s == "direction_created" and p["direction_id"] not in c.directions:
            c.directions[p["direction_id"]] = Direction(p["direction_id"], p["title"], p["description"])
        elif s == "direction_edited" and p["direction_id"] in c.directions:
            d = c.directions[p["direction_id"]]
            d.title, d.description = p["title"], p["description"]
        elif s == "direction_goal_set" and p["direction_id"] in c.directions:
            c.directions[p["direction_id"]].goal = p["goal"]
        elif s in {"direction_archived", "direction_restored"} and p["direction_id"] in c.directions:
            c.directions[p["direction_id"]].archived = s == "direction_archived"
        elif s == "offering_created" and p["offering_id"] not in c.offerings:
            c.offerings[p["offering_id"]] = Offering(
                p["offering_id"], p["format"], p["title"], p["description"], p.get("direction_id")
            )
        elif s == "offering_archived" and p["offering_id"] in c.offerings:
            c.offerings[p["offering_id"]].archived = True
        elif s == "offering_restored" and p["offering_id"] in c.offerings:
            c.offerings[p["offering_id"]].archived = False
        elif s == "offering_direction_set" and p["offering_id"] in c.offerings:
            c.offerings[p["offering_id"]].direction_id = p.get("direction_id")
        elif s == "offering_renamed" and p["offering_id"] in c.offerings:
            c.offerings[p["offering_id"]].title = p["title"]
        elif s == "profile_saved":
            c.activity, c.timezone = p["activity"], p["timezone"]
        elif s == "profile_details_saved":
            c.details, c.details_confirmed = dict(p["details"]), False
        elif s == "profile_details_confirmed" and c.details:
            c.details_confirmed = True
        elif s == "format_toggled":
            (c.formats.add if p["enabled"] else c.formats.discard)(p["format"])
    return c


def _split(arg: str, n_min: int, usage: str) -> list[str]:
    parts = [x.strip() for x in str(arg or "").split("|")]
    if len(parts) < n_min or not all(parts[:n_min]):
        raise ValueError(f"формат: {usage}")
    return parts


def _title(t: str) -> str:
    if len(t) > 80:
        raise ValueError("название длиннее 80 символов")
    return t


def active_directions(c: Catalog, *, archived: bool = False) -> list[Direction]:
    return [d for d in c.directions.values() if d.archived == archived]


def direction_ref(c: Catalog, ref: str, *, archived: bool = False) -> Direction:
    items = active_directions(c, archived=archived)
    ref = str(ref or "").strip()
    if ref.isdigit() and 0 < int(ref) <= len(items):
        return items[int(ref) - 1]
    for d in items:
        if d.title.casefold() == ref.casefold():
            return d
    raise ValueError("направление не найдено, см. /directions" + (" archived" if archived else ""))


def create_direction(c: Catalog, arg: str) -> dict[str, Any] | None:
    parts = _split(arg, 1, "/direction_add Название | описание")
    title = _title(parts[0])
    did = stable_id("dir", title.casefold())
    if did in c.directions:
        return None
    return {"step": "direction_created", "direction_id": did, "title": title, "description": " | ".join(parts[1:])}


def edit_direction(c: Catalog, arg: str) -> dict[str, Any]:
    parts = _split(arg, 2, "/direction_edit N | Название | описание")
    d = direction_ref(c, parts[0])
    return {
        "step": "direction_edited",
        "direction_id": d.direction_id,
        "title": _title(parts[1]),
        "description": " | ".join(parts[2:]) or d.description,
    }


def set_goal(c: Catalog, arg: str) -> dict[str, Any]:
    parts = _split(arg, 2, "/direction_goal N | цель")
    return {"step": "direction_goal_set", "direction_id": direction_ref(c, parts[0]).direction_id, "goal": parts[1]}


def archive(c: Catalog, ref: str, *, restore: bool = False) -> dict[str, Any]:
    d = direction_ref(c, ref, archived=restore)
    return {"step": "direction_restored" if restore else "direction_archived", "direction_id": d.direction_id}


def create_offering(c: Catalog, arg: str) -> dict[str, Any] | None:
    parts = _split(arg, 2, "/offering_add формат | Название | описание [| N направления]")
    fmt = parts[0].casefold()
    fmt = next((k for k, v in FORMATS.items() if fmt in {k, v}), fmt)
    if fmt not in FORMATS:
        raise ValueError("формат: " + ", ".join(FORMATS))
    if fmt not in c.formats:
        raise ValueError(f"формат «{FORMATS[fmt]}» выключен: /format_on {fmt}")
    did = direction_ref(c, parts[3]).direction_id if len(parts) > 3 and parts[3] else None
    oid = stable_id("off", fmt, parts[1].casefold(), did or "")
    if oid in c.offerings and not c.offerings[oid].archived:
        return None
    return {
        "step": "offering_created",
        "offering_id": oid,
        "format": fmt,
        "title": _title(parts[1]),
        "description": parts[2] if len(parts) > 2 else "",
        "direction_id": did,
    }


def bind_offering(c: Catalog, arg: str) -> dict[str, Any] | None:
    """Donor bind/unbind_activity_direction_subject for offerings: ``N | M`` binds, ``N | -`` unbinds."""
    parts = _split(arg, 2, "/offering_direction N предложения | N направления (или -)")
    items = active_offerings(c)
    ref = parts[0].strip()
    if not (ref.isdigit() and 0 < int(ref) <= len(items)):
        raise ValueError("предложение не найдено, см. /offerings")
    o = items[int(ref) - 1]
    did = None if parts[1].strip() == "-" else direction_ref(c, parts[1]).direction_id
    if o.direction_id == did:
        return None
    return {"step": "offering_direction_set", "offering_id": o.offering_id, "direction_id": did}


def active_offerings(c: Catalog) -> list[Offering]:
    return [o for o in c.offerings.values() if not o.archived]


def retire_offering(c: Catalog, ref: str) -> dict[str, Any]:
    items = active_offerings(c)
    if not (str(ref).strip().isdigit() and 0 < int(ref) <= len(items)):
        raise ValueError("предложение не найдено, см. /offerings")
    return {"step": "offering_archived", "offering_id": items[int(ref) - 1].offering_id}


def archived_offerings(c: Catalog) -> list[Offering]:
    return [o for o in c.offerings.values() if o.archived]


def rename_offering(c: Catalog, arg: str) -> dict[str, Any] | None:
    """``N | Новое название`` (donor ``rename_business_offering``); no-op rename emits nothing."""
    parts = _split(arg, 2, "/offering_rename N | Новое название")
    items = active_offerings(c)
    if not (parts[0].isdigit() and 0 < int(parts[0]) <= len(items)):
        raise ValueError("предложение не найдено, см. /offerings")
    o, title = items[int(parts[0]) - 1], _title(parts[1])
    if title == o.title:
        return None
    return {"step": "offering_renamed", "offering_id": o.offering_id, "title": title, "detail": f"{o.title} -> {title}"}


def restore_offering(c: Catalog, ref: str) -> dict[str, Any]:
    """Restore N-th archived offering (donor ``restore_business_offering``); its format must be on."""
    items = archived_offerings(c)
    if not (str(ref).strip().isdigit() and 0 < int(ref) <= len(items)):
        raise ValueError("архивное предложение не найдено")
    o = items[int(ref) - 1]
    if o.fmt not in c.formats:
        raise ValueError(f"формат «{FORMATS[o.fmt]}» выключен: /format_on {o.fmt}")
    return {"step": "offering_restored", "offering_id": o.offering_id}


def toggle_format(c: Catalog, key: str, *, enabled: bool) -> dict[str, Any] | None:
    key = str(key or "").strip().casefold()
    if key not in FORMATS:
        raise ValueError("формат: " + ", ".join(FORMATS))
    if (key in c.formats) == enabled:
        return None
    if not enabled and any(o.fmt == key for o in active_offerings(c)):
        raise ValueError("есть активные предложения в этом формате — сначала /offering_retire")
    return {"step": "format_toggled", "format": key, "enabled": enabled}


def directions_text(c: Catalog, *, archived: bool = False) -> str:
    rows = [
        f"{i}. {d.title}" + (f" — {d.description}" if d.description else "")
        for i, d in enumerate(active_directions(c, archived=archived), 1)
    ]
    head = "📦 Архив направлений" if archived else "🧭 Направления"
    tail = "/direction_restore N" if archived else "/direction N · /direction_add Название | описание"
    return f"{head}\n" + ("\n".join(rows) or "Пока пусто.") + f"\n\n{tail}"


def direction_text(c: Catalog, ref: str) -> str:
    d = direction_ref(c, ref)
    offs = [o for o in active_offerings(c) if o.direction_id == d.direction_id]
    lines = [
        f"🧭 {d.title}",
        d.description or "Без описания.",
        f"🎯 Цель: {d.goal or 'не задана (/direction_goal N | цель)'}",
    ]
    lines.append("Предложения:\n" + ("\n".join(f"• {o.title} ({FORMATS[o.fmt]})" for o in offs) or "• пока нет"))
    lines.append("/direction_edit · /direction_archive (данные сохраняются, можно восстановить)")
    return "\n".join(lines)


def offerings_text(c: Catalog) -> str:
    names = {d.direction_id: d.title for d in c.directions.values()}
    rows = [
        f"{i}. {o.title} — {FORMATS[o.fmt]}" + (f" · {names[o.direction_id]}" if o.direction_id in names else "")
        for i, o in enumerate(active_offerings(c), 1)
    ]
    return (
        "🧪 Предложения\n" + ("\n".join(rows) or "Пока пусто.") + "\n\n/offering_add формат | Название | описание [| N]"
    )


def formats_text(c: Catalog) -> str:
    return (
        "🧩 Форматы\n"
        + "\n".join(f"{'✅' if k in c.formats else '▫️'} {k} — {v}" for k, v in FORMATS.items())
        + ("\n\n/format_on key · /format_off key")
    )


def save_profile(c: Catalog, arg: str) -> dict[str, Any]:
    """``описание деятельности [| часовой пояс]`` (donor ``save_business_profile``)."""
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    parts = _split(arg, 1, "/profile_set описание | Europe/Moscow")
    tz = parts[1] if len(parts) > 1 and parts[1] else c.timezone
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"неизвестный часовой пояс: {tz}") from None
    if len(parts[0]) > 500:
        raise ValueError("описание длиннее 500 символов")
    return {"step": "profile_saved", "activity": parts[0], "timezone": tz}


# donor domain.business_profile.extract_explicit_business_profile_details: explicit facts only, never guessed
_LISTS = (
    ("services", "Услуги", ("услуги", "услуга", "services")),
    ("products", "Продукты", ("продукты", "продукт", "products")),
    ("audiences", "Для кого", ("аудитория", "клиенты", "для кого", "audience")),
    ("geo", "География", ("география", "город", "регион", "geo")),
)
_TEXTS = (
    ("working_hours", "Часы работы", ("часы работы", "график", "working hours")),
    ("booking_rules", "Правила записи", ("правила записи", "запись", "booking rules")),
    ("tone_of_voice", "Стиль общения", ("тон", "стиль общения", "tone of voice")),
    ("sales_terms", "Условия продажи", ("условия продажи", "возврат", "условия возврата")),
)
_PRICE = re.compile(r"(?<!\w)\d[\d\s]{0,8}(?:[.,]\d{1,2})?\s*(?:₽|руб(?:\.|лей|ля)?|RUB|€|\$)", re.IGNORECASE)
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-zА-Яа-я]{2,}(?![\w.-])")
_PHONE = re.compile(r"(?<!\d)(?:\+\d[\d ()-]{8,}\d)(?!\d)")
_HANDLE = re.compile(r"(?<![\w@])@[A-Za-z0-9_]{4,32}\b")


def _norm(items: list[str]) -> list[str]:
    out: list[str] = []
    for x in items:
        v = " ".join(str(x).split())[:120]
        if v and v.casefold() not in {o.casefold() for o in out}:
            out.append(v)
    return out[:12]


def _labeled(text: str, labels: tuple[str, ...]) -> list[str]:
    pat = "|".join(re.escape(x) for x in labels)
    m = re.search(rf"(?im)(?:^|[;.\n])\s*(?:{pat})\s*:\s*([^;\n]+)", text)
    return _norm([x for x in re.split(r",|\|", m.group(1)) if x.strip()]) if m else []


def extract_profile_details(description: str) -> dict[str, Any]:
    """Donor suggest_business_profile_details: deterministic, prefers missing over invented."""
    text = str(description or "").replace("\x00", " ").strip()[:2000]
    out: dict[str, Any] = {k: _labeled(text, labels) for k, _, labels in _LISTS}
    out["prices"] = _norm(_PRICE.findall(text))
    out["contacts"] = _norm([*_EMAIL.findall(text), *_PHONE.findall(text), *_HANDLE.findall(text)])
    for k, _, labels in _TEXTS:
        vals = _labeled(text, labels)
        out[k] = vals[0] if vals else ""
    return {k: v for k, v in out.items() if v}


def save_profile_details(c: Catalog, text: str) -> dict[str, Any] | None:
    """Donor save_business_profile_details (reset_confirmation): None when nothing explicit or unchanged."""
    details = extract_profile_details(text)
    if not details:
        raise ValueError("ничего не распознано: укажите «Услуги: …; Город: …; Цены: 1500 ₽; Контакты: …»")
    return None if details == c.details else {"step": "profile_details_saved", "details": details}


def confirm_profile_details(c: Catalog) -> dict[str, Any] | None:
    if not c.details:
        raise ValueError("сначала /profile_details текст")
    return None if c.details_confirmed else {"step": "profile_details_confirmed"}


def profile_review_lines(details: dict[str, Any]) -> list[str]:
    titles = {k: t for k, t, _ in (*_LISTS, *_TEXTS)} | {"prices": "Цены", "contacts": "Контакты"}
    order = ("services", "products", "prices", "audiences", "geo", "contacts", *(k for k, _, _ in _TEXTS))
    return [
        f"{titles[k]}: {', '.join(v) if isinstance(v, list) else v}" for k in order if (v := details.get(k))
    ]


def profile_review_text(c: Catalog) -> str:
    """Donor profile_review_text: confirm-or-edit boundary before details are used."""
    facts = "\n".join(f"• {x}" for x in profile_review_lines(c.details))
    return (
        "Я правильно понял?\n\n"
        + (c.activity or "Деятельность не описана.")
        + (f"\n\nЯ также выделил из Вашего текста:\n{facts}" if facts else "")
        + "\n\nЕсли что-то неверно — /profile_details заново. Иначе подтвердите: /profile_confirm"
    )


def profile_text(c: Catalog) -> str:
    return (
        f"🏢 Профиль бизнеса\nДеятельность: {c.activity or 'не описана'}\nЧасовой пояс: {c.timezone}\n"
        f"Направлений: {len(active_directions(c))} · предложений: {len(active_offerings(c))}\n"
        + "".join(f"{x}\n" for x in profile_review_lines(c.details))
        + ("✅ Детали подтверждены\n" if c.details_confirmed else "⏳ Детали не подтверждены\n" if c.details else "")
        + "\n/profile_set описание | часовой пояс · /profile_details текст"
    )


def booking_offerings(c: Catalog) -> list[Offering]:
    """Active offerings bookable via slots, sorted like donor ``_active_booking_offerings``."""
    return sorted(active_offerings(c), key=lambda o: (o.title.casefold(), o.offering_id))


def resolve_slot_title(c: Catalog, title: str) -> tuple[str, str | None]:
    """``#N`` -> (offering title, offering_id); stale N fails closed; free text passes through."""
    t = str(title or "").strip()
    if not t.startswith("#"):
        exact = next((o for o in booking_offerings(c) if o.title.casefold() == t.casefold()), None)
        return (exact.title, exact.offering_id) if exact else (t, None)
    items = booking_offerings(c)
    ref = t[1:]
    if not (ref.isdigit() and 0 < int(ref) <= len(items)):
        raise ValueError("предложение для записи не найдено, см. /offerings")
    o = items[int(ref) - 1]
    return o.title, o.offering_id
