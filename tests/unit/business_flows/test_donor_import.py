import argparse
import sqlite3

from application.business_flows import admin as ad
from application.business_flows import bookings as bk
from application.business_flows import partners as pt
from application.business_flows import publications as pb
from application.business_flows import sales as sl
from application.business_flows.projection import flow_payloads
from core.admin import roles_read_model as rr
from scripts.migration import donor_import as tool

SCHEMA = {
    "business_offerings": "id, business_id, title, status",
    "customers": "id, business_id, display_name",
    "business_offering_prices": "id, business_id, offering_id, amount_minor, currency, status, created_at",
    "booking_slots": "id, business_id, offering_id, starts_at, duration_minutes, status, booked_customer_id, created_at, booked_at, cancelled_at, updated_at",
    "business_payments": "id, business_id, amount_minor, currency, status, external_reference, note, created_at, paid_at, refunded_at",
    "clientplatform_sales_leads": "id, business_id, customer_id, source_kind, stage, next_action, due_at, created_at",
    "partner_candidates": "id, business_id, name, tags_json, follower_count, contact_basis, contact_value, competitor, created_at",
    "business_publications": "id, business_id, channel, title, body, status, created_at, scheduled_at, published_at",
    "business_members": "id, business_id, user_id, role, status, created_at",
}
ROWS = {
    "business_offerings": [("o1", "B", "Разбор", "active"), ("o9", "OTHER", "Чужое", "active")],
    "customers": [("c1", "B", "Анна")],
    "business_offering_prices": [("p1", "B", "o1", 150000, "rub", "active", "2026-01-01T10:00:00+00:00")],
    "booking_slots": [
        (
            "s1",
            "B",
            "o1",
            "2027-02-01T12:00:00+00:00",
            60,
            "booked",
            "c1",
            "2026-01-02T00:00:00Z",
            "2026-01-03T00:00:00Z",
            None,
            None,
        ),
        ("s2", "B", "o1", "2027-02-02T12:00:00+00:00", 30, "open", None, "2026-01-02T00:00:00Z", None, None, None),
    ],
    "business_payments": [
        (
            "pay1",
            "B",
            150000,
            "RUB",
            "refunded",
            "INV-7",
            "Разбор",
            "2026-01-04T00:00:00Z",
            "2026-01-04T00:00:00Z",
            "2026-01-05T00:00:00Z",
        )
    ],
    "clientplatform_sales_leads": [
        ("l1", "B", "c1", "telegram", "qualified", "Позвонить", "2027-01-01T09:00:00Z", "2026-01-06T00:00:00Z")
    ],
    "partner_candidates": [
        ("pc1", "B", "Йога-клуб", '["йога","спорт"]', 1200, "public", "@yoga", 0, "2026-01-07T00:00:00Z")
    ],
    "business_publications": [
        ("pub1", "B", "telegram", "Анонс", "Текст", "scheduled", "2026-01-08T00:00:00Z", "2027-03-01T10:00:00Z", None)
    ],
    "business_members": [
        ("m0", "B", 100, "owner", "active", "2026-01-01T00:00:00Z"),
        ("m1", "B", 200, "marketer", "active", "2026-01-09T00:00:00Z"),
    ],
}


def _donor(path):
    conn = sqlite3.connect(path)
    for t, cols in SCHEMA.items():
        conn.execute(f"CREATE TABLE {t} ({cols})")
        for row in ROWS.get(t, []):
            conn.execute(f"INSERT INTO {t} VALUES ({','.join('?' * len(row))})", row)
    conn.commit()
    conn.close()


def _args(donor, apply):
    return argparse.Namespace(donor=str(donor), business_id="B", tenant="t1", owner_user_id="100", apply=apply)


def test_dry_run_writes_nothing_and_apply_is_idempotent(tmp_path, flow):
    _donor(tmp_path / "cp.db")
    store = flow.store
    store.append_event = lambda ev, commit=True: store.events.append(ev)
    store.commit = lambda: None
    dry = tool.run(_args(tmp_path / "cp.db", False), store=store)
    assert dry["mode"] == "dry-run" and store.events == [] and dry["facts_total"] > 0
    assert dry["skipped"] == {"business_members:owner_is_tenant": 1}
    first = tool.run(_args(tmp_path / "cp.db", True), store=store)
    assert first["written"] == dry["facts_total"]
    again = tool.run(_args(tmp_path / "cp.db", True), store=store)
    assert again["written"] == 0 and again["already_imported"] == dry["facts_total"]

    def facts(et):
        return flow_payloads(store, tenant_id="t1", event_type=et)

    slots = sorted(bk.replay(facts("bookings@v1")).values(), key=lambda s: s.starts_at_ms)
    assert [(s.title, s.status, s.customer_id, s.duration_min) for s in slots] == [
        ("Разбор", "booked", "cp:c1", 60),
        ("Разбор", "open", "", 30),
    ]
    adm = ad.replay(facts("business_admin@v1"))
    assert adm.prices == {"Разбор": (150000, "RUB")}
    pay = next(iter(adm.payments.values()))
    assert pay.reference == "INV-7" and pay.refunded_minor == 150000
    lead = next(iter(sl.replay(facts("sales_pipeline@v1")).leads.values()))
    assert lead.name == "Анна" and lead.stage == sl.Stage.QUALIFIED and lead.next_action == "Позвонить"
    assert list(pt.replay(facts("partners@v1")).values())[0].tags == ("йога", "спорт")
    assert [p.status for p in pb.replay(facts("business_admin@v1")).values()] == ["scheduled"]
    assert rr.team_roles_snapshot(store, tenant_id="t1") == {"200": ["marketing"]}


def test_real_sqlite_event_store_roundtrip(tmp_path):
    from runtime.platform.event_store.sqlite_event_store import SqliteEventStore

    _donor(tmp_path / "cp.db")
    with SqliteEventStore(str(tmp_path / "events.db")) as store:
        n = tool.run(_args(tmp_path / "cp.db", True), store=store)["written"]
        assert n > 0 and tool.run(_args(tmp_path / "cp.db", True), store=store)["written"] == 0
        assert len(bk.replay(flow_payloads(store, tenant_id="t1", event_type="bookings@v1"))) == 2


def test_donor_is_opened_read_only(tmp_path):
    _donor(tmp_path / "cp.db")
    before = (tmp_path / "cp.db").read_bytes()
    tool.run(_args(tmp_path / "cp.db", False))
    assert (tmp_path / "cp.db").read_bytes() == before
    assert all(
        r["business_id"] == "B"
        for t in __import__("runtime.platform.donor_db_reader", fromlist=["x"])
        .read_donor(str(tmp_path / "cp.db"), "B")
        .values()
        for r in t
    )
