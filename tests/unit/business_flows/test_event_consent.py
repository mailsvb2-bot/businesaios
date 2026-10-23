from datetime import UTC, datetime, timedelta

import pytest

from application.business_flows import event_consent as ec
from application.business_flows import event_consent as ec_an
from application.business_flows import public_events as pe

NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)


def _setup():
    f = [pe.create_event(title="Вебинар", starts_at=NOW + timedelta(days=2), timezone_name="Europe/Moscow", now=NOW)]
    f.append(pe.publish(pe.replay(f), f[0]["event_id"], now=NOW))
    fact, token = pe.register(pe.replay(f), slug=f[0]["slug"], name="A", email="a@b.ru", consent=True, now=NOW)
    return f + [fact], fact["registration_id"], token


def test_channels_and_text():
    assert ec.normalize_channels(["Email", "vk", "email", ""]) == ("email", "vk")
    with pytest.raises(ValueError):
        ec.normalize_channels(["sms"])
    with pytest.raises(ValueError):
        ec.normalize_channels([])
    assert ec.advertiser_label(" ", "ООО  Ромашка") == "ООО Ромашка"
    assert "«Ромашка»" in ec.consent_text("Ромашка")
    with pytest.raises(ValueError):
        ec.consent_text("")


def test_grant_and_revoke():
    f, rid, token = _setup()
    b = pe.replay(f)
    with pytest.raises(ValueError):
        ec.grant(b, registration_id=rid, channels=["email"], label="Ромашка", expected_sha256="x", now=NOW)
    g = ec.grant(
        b,
        registration_id=rid,
        channels=["email", "vk"],
        label="Ромашка",
        expected_sha256=ec.text_sha256("Ромашка"),
        now=NOW,
    )
    f.append(g)
    assert ec.active_channels(f, rid) == ("email", "vk")
    assert ec.is_authorized(f, rid, "VK") and not ec.is_authorized(f, rid, "telegram")
    out = ec.revoke_by_token(b, f, token)
    assert out[0]["step"] == "event_commercial_consent_revoked" and out[1]["step"] == "event_dispatch_cancelled"
    f += out
    assert ec.active_channels(f, rid) == ()
    assert [o["step"] for o in ec.revoke_by_token(b, f, token)] == ["event_dispatch_cancelled"]
    with pytest.raises(ValueError):
        ec.revoke_by_token(b, f, "nope")


NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)


def test_funnel_and_payment():
    f = [pe.create_event(title="Вебинар", starts_at=NOW + timedelta(days=2), timezone_name="UTC", now=NOW)]
    eid = f[0]["event_id"]
    f.append(pe.publish(pe.replay(f), eid, now=NOW))
    regs = []
    for m in ("a@b.ru", "c@d.ru"):
        fact, _ = pe.register(pe.replay(f), slug=f[0]["slug"], name="X", email=m, consent=True, now=NOW)
        f.append(fact)
        regs.append(fact["registration_id"])
    f += [
        ec_an.mark(regs[0], "join_clicked"),
        ec_an.mark(regs[0], "attendance_confirmed"),
        ec_an.mark(regs[0], "join_clicked"),
    ]
    with pytest.raises(ValueError):
        ec_an.mark(regs[0], "x")
    out = ec_an.link_verified_payment(
        f, event_id=eid, registration_id=regs[0], payment_ref="p1", amount_minor=500, currency="rub", occurred_at=NOW
    )
    assert out[-1]["reason"] == "event_offer_paid"
    f += out
    again = ec_an.link_verified_payment(
        f, event_id=eid, registration_id=regs[0], payment_ref="p1", amount_minor=500, currency="RUB", occurred_at=NOW
    )
    assert [x["step"] for x in again] == ["event_dispatch_cancelled"]
    fn = ec_an.funnel(f, eid)
    assert (fn.registered, fn.join_clicked, fn.paid, fn.revenue) == (2, 1, 1, (("RUB", 500),))
    assert fn.join_click_rate == 0.5 and fn.registration_to_paid_rate == 0.5 and fn.confirmed_attendance_rate == 0.5
    for kw in (
        {"amount_minor": 1, "currency": None},
        {"amount_minor": -1, "currency": "RUB"},
        {"amount_minor": None, "currency": "RUBL"},
    ):
        with pytest.raises(ValueError):
            ec_an.link_verified_payment(
                f, event_id=eid, registration_id=regs[1], payment_ref="p2", occurred_at=NOW, **kw
            )
    with pytest.raises(ValueError):
        ec_an.link_verified_payment(
            f,
            event_id="x",
            registration_id=regs[1],
            payment_ref="p2",
            amount_minor=None,
            currency=None,
            occurred_at=NOW,
        )
