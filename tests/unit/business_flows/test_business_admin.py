import pytest

from application.business_flows import admin as ad
from runtime.handler_impl.domains import business_flow_ops as ops


def test_money_parsing() -> None:
    assert ad.parse_money("1500") == (150000, "RUB")
    assert ad.parse_money("12,5 usd") == (1250, "USD")
    assert ad.money(150050, "RUB") == "1500,50 ₽"
    for bad in ("", "0", "abc", "10 XXX", "1.234"):
        with pytest.raises(ValueError):
            ad.parse_money(bad)


def test_settings_autopilot_prices(flow) -> None:
    _, text = flow.run(ops.handle_business_admin, op="setting", arg="greeting = Привет")
    assert "greeting = Привет" in text
    _, text = flow.run(ops.handle_business_admin, op="autopilot", arg="on")
    assert "включён" in text
    _, text = flow.run(ops.handle_business_admin, op="autopilot", arg="on")
    assert "без изменений" in text
    flow.run(ops.handle_business_admin, op="price", arg="Консультация | 3000")
    _, text = flow.run(ops.handle_business_admin, op="price")
    assert "Консультация — 3000,00 ₽" in text
    _, text = flow.run(ops.handle_business_admin, op="setting", arg="BAD KEY = x")
    assert "Не получилось" in text


def test_payments_idempotent_and_refund_bounded(flow) -> None:
    flow.run(ops.handle_business_admin, op="price", arg="Консультация | 3000")
    _, text = flow.run(ops.handle_business_admin, op="pay", arg="Консультация | 3000 | P-1")
    assert "3000,00 ₽" in text
    _, text = flow.run(ops.handle_business_admin, op="pay", arg="Консультация | 3000 | p-1")
    assert "уже записан" in text
    _, text = flow.run(ops.handle_business_admin, op="pay", arg="Консультация | 10 | P-1")
    assert "different_terms" in text
    _, text = flow.run(ops.handle_business_admin, op="pay", arg="Чужое | 10 | P-2")
    assert "offering_unknown" in text
    flow.run(ops.handle_business_admin, op="refund", arg="P-1 | 1000 | R-1")
    _, text = flow.run(ops.handle_business_admin, op="refund", arg="P-1 | 1000 | R-1")
    assert "уже записан" in text
    _, text = flow.run(ops.handle_business_admin, op="refund", arg="P-1 | 2500 | R-2")
    assert "refund_exceeds_remaining" in text
    _, text = flow.run(ops.handle_business_admin, op="summary")
    assert "1 шт., получено 3000,00 ₽, возвраты 1000,00 ₽, итого 2000,00 ₽" in text


def test_approval_state_machine() -> None:
    req = ad.request_approval("Поднять бюджет рекламы", 50000, "RUB", source_ref="ads:1")
    st = ad.replay([req, ad.request_approval("dup", 1, "RUB", source_ref="ads:1")])
    assert len(st.approvals) == 1
    with pytest.raises(ValueError):
        ad.decide_approval(st, "revoke", "1")
    st = ad.replay([req, ad.decide_approval(st, "approve", "1")])
    assert "одобрено" in ad.format_approval(1, st.approvals[req["approval_id"]])
    st = ad.replay(
        [
            req,
            {"step": "approval_decided", "approval_id": req["approval_id"], "status": "approved"},
            ad.decide_approval(st, "revoke", "1"),
        ]
    )
    assert list(st.approvals.values())[0].status == "revoked"
    with pytest.raises(ValueError):
        ad.decide_approval(st, "approve", "1")


def test_admin_routes_owner_only() -> None:
    from core.policies.telegram.routes.business_flow_routes import handle_business_flow_routes

    class Ctx:
        cmd, args, callback_data, is_admin = "/pay", "X | 1 | r", "", True

    assert handle_business_flow_routes(Ctx(), user_id="u1").action == "business_admin@v1"
    Ctx.is_admin = False
    assert handle_business_flow_routes(Ctx(), user_id="u1") is None


# --- business retirement: two-step, flag off by default, archive without data loss ---
def test_business_retire_two_step_flag_off_dry_run_then_archive_and_restore():
    from datetime import UTC, datetime, timedelta

    t0 = datetime(2026, 10, 24, 10, 0, tzinfo=UTC)
    on, off = {ad.RETIRE_ENV: "1"}, {}
    log: list[dict] = [{"step": "payment_recorded", "amount_minor": 500}]  # existing business data
    assert ad.retire_status(log)["status"] == "active" and not ad.is_archived(log)
    req, code = ad.retire_request(log, name="Студия", nonce="a1b2c3d4", now=t0)
    assert code == "A1B2C3D4" and "A1B2C3D4" not in str(req)  # only the hash is stored
    log.append(req)
    assert ad.retire_status(log, t0)["status"] == "pending"
    text = ad.retire_confirm_text("Студия", code)
    assert "/business_retire_confirm A1B2C3D4" in text and "не удаляются" in text and "/business_restore" in text
    for bad in ("WRONG", ""):
        with pytest.raises(ValueError):
            ad.retire_confirm(log, code=bad, now=t0, env=on)
    with pytest.raises(ValueError):  # expired code
        ad.retire_confirm(log, code=code, now=t0 + timedelta(seconds=301), env=on)
    dry = ad.retire_confirm(log, code=code.lower(), now=t0, env=off)  # flag off: recorded, nothing archived
    assert dry["step"] == "business_retire_dry_run"
    log.append(dry)
    assert not ad.is_archived(log) and "выключено" in ad.retire_result_text("Студия", dry_run=True)
    fact = ad.retire_confirm(log, code=code, now=t0, env=on)
    assert fact["step"] == "business_archived" and fact["data_preserved"] is True
    log.append(fact)
    assert ad.is_archived(log) and any(p["step"] == "payment_recorded" for p in log)  # data intact
    assert ad.retire_confirm(log, code=code, now=t0, env=on) is None  # idempotent
    with pytest.raises(ValueError):
        ad.retire_request(log, name="Студия", nonce="a1b2c3d4", now=t0)
    log.append(ad.business_restore(log, t0))
    assert ad.retire_status(log)["status"] == "active" and ad.business_restore(log, t0) is None
    r2, _ = ad.retire_request(log, name="Студия", nonce="00000001", now=t0)
    log.append(r2)
    log.append(ad.retire_cancel(log, t0))
    assert ad.retire_status(log, t0)["status"] == "active" and ad.retire_cancel(log, t0) is None
