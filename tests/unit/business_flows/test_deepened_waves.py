from __future__ import annotations

from functools import partial

from application.business_flows import partners as pt
from core.policies.telegram.routes.business_flow_routes import BUSINESS_FLOW_COMMANDS
from runtime.handler_impl.domains import bot_provisioning_ops as bops
from runtime.handler_impl.domains import business_flow_ops as ops
from runtime.platform.event_store.sqlite_event_store import SqliteEventStore

NOW = 1_800_000_000_000
H = 3_600_000


def test_reminder_dispatch_pushes_to_each_participant_once(flow) -> None:
    run = partial(flow.run, partial(ops.handle_bookings, now_ms=NOW))
    run(op="add_slot", arg="2027-01-15 14:00 Консультация")  # 3h ahead -> 24h reminder due
    flow.run(partial(ops.handle_bookings, now_ms=NOW), op="book", arg="1", user_id="c7")
    _, text = flow.run(partial(ops.handle_bookings, now_ms=NOW), op="dispatch")
    pushes = [m for m in flow.effects.sent if "Напоминание" in m["text"]]
    assert pushes and all(m["user_id"] == "c7" for m in pushes)
    assert "Напоминаний отправлено: 1 из 1" in text
    _, text = flow.run(partial(ops.handle_bookings, now_ms=NOW), op="dispatch")
    assert "0 из 0" in text


def test_bot_attach_and_getme_verify(flow, monkeypatch) -> None:
    monkeypatch.setenv("SHOP_BOT_TOKEN", "1:x")
    flow.run(bops.handle_bot_provisioning, op="request", arg="@shop_bot")
    flow.run(bops.handle_bot_provisioning, op="attach", arg="env:SHOP_BOT_TOKEN")
    seen = {}

    def check(token, **_):
        seen["t"] = token
        return {"ok": True, "bot": {"id": 5, "is_bot": True, "username": "Shop_Bot"}}

    flow.effects.telegram_self_check = check
    _, text = flow.run(bops.handle_bot_provisioning, op="verify")
    assert seen["t"] == "1:x" and "подключён" in text
    assert flow.store.events[-1]["payload"]["bot_id"] == 5
    assert "1:x" not in str(flow.store.events)


def test_bot_verify_mismatch_fails(flow, monkeypatch) -> None:
    monkeypatch.setenv("SHOP_BOT_TOKEN", "1:x")
    flow.run(bops.handle_bot_provisioning, op="request", arg="@shop_bot")
    flow.run(bops.handle_bot_provisioning, op="attach", arg="env:SHOP_BOT_TOKEN")
    flow.effects.telegram_self_check = lambda token, **_: {"bot": {"id": 1, "is_bot": True, "username": "other_bot"}}
    _, text = flow.run(bops.handle_bot_provisioning, op="verify")
    assert "getme_username_mismatch" in text


def test_partner_pipeline_pitch_and_referral(flow) -> None:
    flow.run(ops.handle_partners, op="add", arg="Кофейня Зерно | кофе | 9000 | existing | @zerno")
    _, text = flow.run(ops.handle_partners, op="status", arg="1 prepared")
    assert "Кофейня Зерно" in text
    _, text = flow.run(ops.handle_partners, op="status", arg="1 agreed")
    assert "Не получилось" in text
    _, text = flow.run(ops.handle_partners, op="pitch", arg="1 Школа | Вебинар")
    assert "Вебинар" in text and "сами" in text
    _, text = flow.run(ops.handle_partners, op="ref", arg="1")
    token = text.rsplit("ref_", 1)[1]
    known = pt.replay([e["payload"] for e in flow.store.events])
    assert pt.resolve_referral(known, "t1", token).name == "Кофейня Зерно"


def test_routes_registered() -> None:
    for cmd in (
        "/send_reminders",
        "/bot_secret",
        "/verify_bot",
        "/partner_status",
        "/partner_pitch",
        "/partner_ref",
    ):
        assert cmd in BUSINESS_FLOW_COMMANDS


def test_sqlite_pd_deletion_erases_derived_state(tmp_path) -> None:
    with SqliteEventStore(str(tmp_path / "e.db")) as es:
        _erase(es)


def _erase(es) -> None:
    db = es._db
    db.execute("INSERT INTO user_state VALUES ('t1','u1','{}',1)")
    es.upsert_user_features_daily(tenant_id="t1", user_id="u1", day_key="d", features_json="{}", created_at_ms=1)
    db.execute("INSERT INTO user_state VALUES ('t1','u2','{}',1)")
    db.commit()
    es.delete_user_events(tenant_id="t1", user_id="u1")
    assert db.execute("SELECT user_id FROM user_state").fetchall() == [("u2",)]
    assert db.execute("SELECT COUNT(1) FROM user_features_daily").fetchone()[0] == 0
