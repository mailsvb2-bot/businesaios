"""Native (VK/MAX) customer menu: deterministic screens over bookings facts.

Port of donor application/native_customer_interactions. Pure: ``respond`` returns
``(screen, facts)``; the screen is materialized by the executor's outbox under
``interaction_key`` (idempotent per provider event). Booking reuses ``bookings.book``.
Training programs are out of scope, so those buttons are not offered.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from application.business_flows import bookings as bk

PREFIX = "cpi:"
SLOT_PAGE = 6
_INT = re.compile(r"0|[1-9][0-9]{0,4}")
_ACTIONS = frozenset({"menu", "slots", "book"})
_ALIASES = {
    **dict.fromkeys(("start", "/start", "начать", "меню", "главное меню"), ("menu", ())),
    **dict.fromkeys(("запись", "записаться", "доступная запись", "свободное время"), ("slots", ("0",))),
}
Rows = tuple[tuple[tuple[str, str], ...], ...]
_MENU_ROW = (("🏠 Меню", "cpi:menu"),)


@dataclass(frozen=True)
class Screen:
    text: str
    rows: Rows


def _b(label: str, cmd: str) -> tuple[str, str]:
    return label[:40], cmd


def parse(value: object) -> tuple[str, tuple[str, ...]] | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    alias = _ALIASES.get(" ".join(raw.casefold().replace("ё", "е").split()))
    if alias:
        return alias
    if not raw.casefold().startswith(PREFIX):
        return None
    parts = raw.split(":")
    if len(parts) < 2 or any(not p for p in parts) or parts[1].strip().casefold() not in _ACTIONS:
        return "stale", ()
    return parts[1].strip().casefold(), tuple(p.strip() for p in parts[2:])


def is_input(value: object) -> bool:
    return parse(value) is not None


def menu(*, linked: bool = False) -> Screen:
    head = "✅ Канал подключён к Вашей карточке клиента.\n\n" if linked else ""
    return Screen(head + "Здесь можно выбрать доступное время записи.", ((_b("📅 Доступная запись", "cpi:slots:0"),),))


def stale() -> Screen:
    return Screen("Эта кнопка уже неактуальна. Откройте нужный раздел заново.", (_MENU_ROW,))


def uuid_token(value: str) -> str:
    """Donor control_callbacks: 22-char urlsafe token for a UUID (fits Telegram's 64-byte callback_data)."""
    return base64.urlsafe_b64encode(UUID(str(value)).bytes).decode("ascii").rstrip("=")


def token_uuid(value: str) -> str:
    padded = str(value) + "=" * (-len(str(value)) % 4)
    return str(UUID(bytes=base64.urlsafe_b64decode(padded.encode("ascii"))))


def page_index(raw: str | None) -> int | None:
    v = str(raw or "").strip()
    return int(v) if _INT.fullmatch(v) else None


def window(items: list[Any], page: int, size: int) -> tuple[list[Any], int, int]:
    if page < 0:
        raise ValueError("page must be non-negative")
    count = max(1, (len(items) + size - 1) // size)
    if page >= count:
        raise IndexError("page is outside result set")
    return items[page * size : page * size + size], page, count


def slots_screen(slots: dict[str, bk.Slot], *, page: int, now_ms: int, tz: str = "Europe/Moscow") -> Screen:
    open_ = bk.upcoming(slots, now_ms=now_ms, status="open")
    if not open_:
        return Screen("Сейчас свободного времени нет. Специалист сможет добавить его позже.", (_MENU_ROW,))
    cur, i, n = window(open_, page, SLOT_PAGE)
    rows: list[tuple[tuple[str, str], ...]] = [(_b(bk.fmt(s, tz), f"cpi:book:{s.slot_id}"),) for s in cur]
    nav = [_b("⬅️ Назад", f"cpi:slots:{i - 1}")] * (i > 0) + [_b("Вперёд ➡️", f"cpi:slots:{i + 1}")] * (i + 1 < n)
    rows += [tuple(nav)] * bool(nav) + [_MENU_ROW]
    text = "Доступная запись\n\n" + "\n".join(f"• {bk.fmt(s, tz)}" for s in cur) + f"\n\nСтраница {i + 1}/{n}"
    return Screen(text, tuple(rows))


def booked_screen(slot: bk.Slot, tz: str = "Europe/Moscow") -> Screen:
    return Screen(f"✅ Запись подтверждена.\n\n{bk.fmt(slot, tz)}", ((_b("📅 Другие свободные окна", "cpi:slots:0"),), _MENU_ROW))


def unavailable() -> Screen:
    return Screen("Это время уже недоступно. Показываю актуальные варианты.", ((_b("📅 Открыть свободное время", "cpi:slots:0"),), _MENU_ROW))


def resolve(action: str, args: tuple[str, ...], slots: dict[str, bk.Slot], *, customer_id: str, now_ms: int) -> tuple[Screen, list[dict[str, Any]]]:
    if action == "menu":
        return menu(), []
    if action == "slots":
        page = page_index(args[0] if len(args) == 1 else None)
        if page is None:
            return stale(), []
        try:
            return slots_screen(slots, page=page, now_ms=now_ms), []
        except IndexError:
            return stale(), []
    if action == "book" and len(args) == 1:
        try:
            fact = bk.book(slots, slots.get(args[0]), customer_id=customer_id, now_ms=now_ms)
        except ValueError:
            return unavailable(), []
        return booked_screen(slots[args[0]]), [fact]
    return stale(), []


def respond(*, identity: dict[str, Any], route: dict[str, Any], raw_text: object, provider_event_id: str,
            slots: dict[str, bk.Slot], now_ms: int, linked: bool = False) -> dict[str, Any] | None:
    """``customer_screen`` fact (+ booking facts) or None when the input is not a menu command."""
    if identity.get("status") != "active":
        raise ValueError("native customer interaction requires an active identity")
    if identity.get("business_id") != route.get("business_id"):
        raise ValueError("native customer identity belongs to another business")
    if identity.get("platform") != route.get("platform"):
        raise ValueError("native customer identity platform does not match route")
    parsed = ("menu", ()) if linked else parse(raw_text)
    if parsed is None:
        return None
    eid = str(provider_event_id or "").strip()
    if not eid or len(eid) > 160:
        raise ValueError("provider_event_id must be 1..160 characters")
    cid = str(identity["customer_id"])
    screen, facts = (menu(linked=True), []) if linked else resolve(*parsed, slots, customer_id=cid, now_ms=now_ms)
    return {
        "step": "customer_screen", "business_id": route["business_id"], "connection_id": route.get("connection_id"),
        "customer_id": cid, "platform": route["platform"], "text": screen.text,
        "rows": [[list(b) for b in r] for r in screen.rows],
        "interaction_key": f"{route.get('route_id', '')}:{eid}:customer-ui-v1", "facts": facts,
    }
