from datetime import UTC, datetime, timedelta

import pytest

from application.business_flows import event_consent as ec
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
    g = ec.grant(b, registration_id=rid, channels=["email", "vk"], label="Ромашка",
                 expected_sha256=ec.text_sha256("Ромашка"), now=NOW)
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
