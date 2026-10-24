from application.business_flows import cockpit as cp
from application.business_flows import customer_timeline_sources as cts
from application.business_flows import sales as sl

T0 = 1_790_000_000_000


def _timed():
    return [
        (T0, {"step": "lead_inbound", "lead_id": "L1", "name": "Анна", "source": "telegram",
              "customer_id": "cust-000042", "note": "💬 хочу на йогу"}),
        (T0 + 60_000, {"step": "lead_event", "lead_id": "L1", "event": "contact", "stage": "engaged"}),
        (T0 + 120_000, {"step": "lead_inbound", "lead_id": "L2", "name": "Б", "customer_id": "other"}),
        (T0 + 180_000, {"step": "followup_optout", "lead_id": "L1"}),
    ]


def test_sales_entries_bound_to_customer_only():
    st = sl.replay([p for _, p in _timed()])
    es = cts.customer_sales_entries("cust-000042", _timed(), st)
    assert [e.title for e in es] == ["Добавлена заметка", "Новое обращение", "Связались с клиентом",
                                     "Клиент попросил не писать"]
    assert cts.customer_sales_entries("nobody", _timed(), st) == []


def test_cockpit_history_screen_shows_live_sales_facts_without_bookings():
    st = sl.replay([p for _, p in _timed()])
    snap = cp.Snapshot(sales=st, sales_rows=_timed(), now_ms=T0 + 10**6)
    text, _ = cp.render(cp.parse("cpm:cust-time:cust-000042"), snap, is_owner=True)
    assert "История клиента 000042" in text and "Связались с клиентом" in text and "хочу на йогу" in text
