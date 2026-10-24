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


def test_eg_registration_urls():
    slug = "a" * 32
    assert ec.registration_url(public_base_url="https://x.ru/", public_slug=slug) == f"https://x.ru/e/{slug}"
    u = ec.yandex_registration_url(public_base_url="https://x.ru", public_slug=slug, external_campaign_id=" 123 ")
    assert u.endswith("?source=yandex_direct&campaign_ref=123")
    for bad in ("http://x.ru", "https://u:p@x.ru", "https://x.ru/a\nb"):
        with pytest.raises(ValueError):
            ec.registration_url(public_base_url=bad, public_slug=slug)
    with pytest.raises(ValueError):
        ec.registration_url(public_base_url="https://x.ru", public_slug="short")
    with pytest.raises(ValueError):
        ec.yandex_registration_url(public_base_url="https://x.ru", public_slug=slug, external_campaign_id="012")
    with pytest.raises(ValueError):
        ec.registration_url(public_base_url="https://x.ru", public_slug=slug, source="s" * 161)


def test_eg_breakdown_and_roas():
    f, rid, _ = _setup()
    b = pe.replay(f)
    r2, _ = pe.register(b, slug=f[0]["slug"], name="B", email="b@b.ru", consent=True, now=NOW,
                        source="yandex_direct", campaign_ref="77")
    r3, _ = pe.register(b, slug=f[0]["slug"], name="C", email="c@b.ru", consent=True, now=NOW,
                        source=" yandex_direct ", campaign_ref="77")
    f += [r2, r3, ec_an.mark(r2["registration_id"], "join_clicked")]
    f += ec_an.link_verified_payment(f, event_id=f[0]["event_id"], registration_id=r3["registration_id"],
                                     payment_ref="p1", amount_minor=500000, currency="RUB", occurred_at=NOW)
    slices = ec.acquisition_breakdown(f, f[0]["event_id"])
    assert [(s.source, s.campaign_ref, s.funnel.registered) for s in slices] == [("yandex_direct", "77", 2), ("direct", None, 1)]
    ya = slices[0]
    assert ya.funnel.join_clicked == 1 and ya.funnel.paid == 1 and slices[1].funnel.paid == 0
    assert ya.funnel.join_click_rate == 0.5 and ya.funnel.offer_click_rate == 0.0 and ya.funnel.registration_to_paid_rate == 0.5
    roi = ec.event_roas(ya, spend_minor=200000, currency="rub")
    assert (roi.roas, roi.profit_after_ad_spend_minor) == (2.5, 300000)
    assert ec.event_roas(ya, spend_minor=0, currency="USD").roas is None
    with pytest.raises(ValueError):
        ec.event_roas(ya, spend_minor=-1, currency="RUB")
