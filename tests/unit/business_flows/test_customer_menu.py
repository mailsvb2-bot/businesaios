import pytest

from application.business_flows import bookings as bk
from application.business_flows import customer_menu as cm

NOW = 1_800_000_000_000
ID = {"status": "active", "business_id": "b", "platform": "vk", "customer_id": "c1"}
ROUTE = {"business_id": "b", "platform": "vk", "route_id": "r1", "connection_id": "k"}


def _slots(n=8):
    return bk.replay([{"step": "slot_opened", "slot_id": f"s{i}", "title": "Сессия", "starts_at_ms": NOW + (i + 1) * 3_600_000,
                       "duration_min": 60} for i in range(n)])


def test_parse():
    assert cm.parse("Меню") == ("menu", ())
    assert cm.parse("записаться") == ("slots", ("0",))
    assert cm.parse("cpi:book:s1") == ("book", ("s1",))
    assert cm.parse("cpi:programs:0") == ("stale", ())
    assert cm.parse("привет") is None and not cm.is_input("")


def test_slots_paging_and_booking():
    s = _slots()
    scr, _ = cm.resolve("slots", ("0",), s, customer_id="c1", now_ms=NOW)
    assert "Страница 1/2" in scr.text and scr.rows[-2] == (("Вперёд ➡️", "cpi:slots:1"),)
    assert cm.resolve("slots", ("5",), s, customer_id="c1", now_ms=NOW)[0] == cm.stale()
    scr, facts = cm.resolve("book", ("s0",), s, customer_id="c1", now_ms=NOW)
    assert facts[0]["step"] == "booked" and scr.text.startswith("✅")
    assert cm.resolve("book", ("nope",), s, customer_id="c1", now_ms=NOW) == (cm.unavailable(), [])


def test_respond_guards_and_key():
    f = cm.respond(identity=ID, route=ROUTE, raw_text="меню", provider_event_id="e1", slots={}, now_ms=NOW)
    assert f["interaction_key"] == "r1:e1:customer-ui-v1" and f["facts"] == []
    assert cm.respond(identity=ID, route=ROUTE, raw_text="hi", provider_event_id="e", slots={}, now_ms=NOW) is None
    assert "подключён" in cm.respond(identity=ID, route=ROUTE, raw_text="", provider_event_id="e", slots={}, now_ms=NOW, linked=True)["text"]
    with pytest.raises(ValueError):
        cm.respond(identity={**ID, "business_id": "x"}, route=ROUTE, raw_text="меню", provider_event_id="e", slots={}, now_ms=NOW)
    with pytest.raises(ValueError):
        cm.respond(identity=ID, route=ROUTE, raw_text="меню", provider_event_id="", slots={}, now_ms=NOW)
