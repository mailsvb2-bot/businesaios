"""Owner booking lifecycle + public storefront connection (port of donor owner_booking_journey).

Pure: returns ``bookings@v1`` / ``sales_pipeline@v1`` facts for the executor to append.
Customer cards are created only through the injected canonical CRM ``ensure_customer``
(executor ``ensure_customer_identity``); nothing here writes or sends.
"""

from __future__ import annotations

from collections.abc import Callable, Collection
from typing import Any

from application.business_flows import bookings as bk
from application.business_flows.projection import stable_id

CANON_OWNER_BOOKING_JOURNEY = True
BOOKED_CANCEL = "На это время уже записан клиент. Сначала свяжитесь с ним — занятую запись нельзя удалить молча."
BOOKED_REPLACE = "На это время уже записан клиент. Занятую запись нельзя перенести без согласования с клиентом."
STAFF_LINK = ("Это публичная ссылка для клиентов. Владелец и сотрудники могут проверить её "
              "через кнопку «Посмотреть глазами клиента».")


def owner_slot(slots: dict[str, bk.Slot], slot_id: str) -> bk.Slot:
    slot = slots.get(str(slot_id or ""))
    if slot is None:
        raise ValueError("slot_not_found")
    return slot


def cancel_slot(slots: dict[str, bk.Slot], slot_id: str) -> dict[str, Any] | None:
    """Close an unclaimed slot; booked slots are refused, already-closed is a no-op (None)."""
    slot = owner_slot(slots, slot_id)
    if slot.status == "booked":
        raise ValueError(BOOKED_CANCEL)
    if slot.status != "open":
        return None
    return {"step": "slot_closed", "slot_id": slot.slot_id}


def replace_slot(slots: dict[str, bk.Slot], slot_id: str, local_start: str, duration_minutes: int, *,
                 now_ms: int, tz: str = "Europe/Moscow") -> list[dict[str, Any]]:
    """Close one open slot and open its replacement in the same fact batch (atomic append)."""
    old = owner_slot(slots, slot_id)
    if old.status == "booked":
        raise ValueError(BOOKED_REPLACE)
    if old.status != "open":
        raise ValueError("Изменять можно только свободное опубликованное время")
    new = bk.parse_slot(f"{local_start} {int(duration_minutes)} {old.title}", now_ms=now_ms, tz=tz)
    return [{"step": "slot_closed", "slot_id": old.slot_id}, new]


def is_storefront_staff(staff_user_ids: Collection[str], telegram_user_id: int) -> bool:
    if isinstance(telegram_user_id, bool) or not isinstance(telegram_user_id, int) or telegram_user_id <= 0:
        raise ValueError("telegram_user_id must be a positive integer")
    return str(telegram_user_id) in {str(x) for x in staff_user_ids}


def connect_storefront_customer(
    sales_payloads: list[dict[str, Any]], *, staff_user_ids: Collection[str], business_active: bool,
    business_name: str, telegram_user_id: int, display_name: str | None,
    ensure_customer: Callable[..., str],
) -> tuple[dict[str, str], dict[str, Any] | None]:
    """Link a public-link visitor as a customer; one stable storefront lead, replay-safe inbound fact."""
    if is_storefront_staff(staff_user_ids, telegram_user_id):
        raise ValueError(STAFF_LINK)
    if not business_active:
        raise LookupError("Публичная страница этого бизнеса больше недоступна")
    uid = str(telegram_user_id)
    customer_id = ensure_customer(channel="telegram", external_subject=uid, display_name=display_name)
    key = f"public-storefront-open:{uid}"
    seen = {str(p.get("dedupe_key")) for p in sales_payloads if p.get("step") == "lead_inbound"}
    fact = None if key in seen else {
        "step": "lead_inbound", "lead_id": stable_id("lead", f"public-storefront:telegram:{uid}"),
        "name": (str(display_name or "").strip() or f"Клиент {uid[-6:]}")[:80], "source": "telegram",
        "surface": "public_storefront", "customer_id": customer_id, "dedupe_key": key,
    }
    return {"business_name": business_name, "customer_id": customer_id}, fact


__all__ = [
    "CANON_OWNER_BOOKING_JOURNEY", "cancel_slot", "connect_storefront_customer", "is_storefront_staff",
    "owner_slot", "replace_slot",
]
