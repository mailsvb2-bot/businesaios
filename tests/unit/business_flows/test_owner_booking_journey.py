import pytest

from application.business_flows import bookings as bk
from application.business_flows import owner_booking_journey as ob

NOW = 1_790_000_000_000


def _slots(status="open"):
    return {"s1": bk.Slot("s1", "Йога", NOW + 86_400_000, 60, status=status, customer_id="c" if status == "booked" else "")}


def test_cancel_and_replace_guards():
    assert ob.cancel_slot(_slots(), "s1") == {"step": "slot_closed", "slot_id": "s1"}
    assert ob.cancel_slot(_slots("closed"), "s1") is None
    with pytest.raises(ValueError, match="уже записан"):
        ob.cancel_slot(_slots("booked"), "s1")
    with pytest.raises(ValueError, match="slot_not_found"):
        ob.owner_slot({}, "x")
    facts = ob.replace_slot(_slots(), "s1", "2027-03-01 10:00", 45, now_ms=NOW)
    assert facts[0]["step"] == "slot_closed" and facts[1]["duration_min"] == 45 and facts[1]["title"] == "Йога"
    for st in ("booked", "closed"):
        with pytest.raises(ValueError):
            ob.replace_slot(_slots(st), "s1", "2027-03-01 10:00", 45, now_ms=NOW)


def test_storefront_connect_is_idempotent_and_refuses_staff():
    calls = []

    def ensure(**kw):
        calls.append(kw)
        return "cust-1"
    kw = dict(staff_user_ids={"1"}, business_active=True, business_name="Кофейня", telegram_user_id=77,
              display_name="Оля", ensure_customer=ensure)
    link, fact = ob.connect_storefront_customer([], **kw)
    assert link["customer_id"] == "cust-1" and fact["dedupe_key"] == "public-storefront-open:77"
    assert ob.connect_storefront_customer([fact], **kw)[1] is None
    assert calls[0] == {"channel": "telegram", "external_subject": "77", "display_name": "Оля"}
    with pytest.raises(ValueError, match="публичная"):
        ob.connect_storefront_customer([], **{**kw, "telegram_user_id": 1})
    with pytest.raises(LookupError):
        ob.connect_storefront_customer([], **{**kw, "business_active": False})
    with pytest.raises(ValueError):
        ob.is_storefront_staff({"1"}, True)
