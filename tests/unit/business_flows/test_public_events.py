from datetime import UTC, datetime, timedelta

import pytest

from application.business_flows import public_events as pe

NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)


def test_lifecycle_and_registration():
    f = [
        pe.create_event(
            title="Вебинар",
            starts_at=NOW + timedelta(days=2),
            timezone_name="Europe/Moscow",
            join_url="https://telemost.yandex.ru/j/1",
            now=NOW,
        )
    ]
    assert f[0]["provider_key"] == "yandex_telemost"
    b = pe.replay(f)
    eid, slug = f[0]["event_id"], f[0]["slug"]
    with pytest.raises(ValueError):
        pe.register(b, slug=slug, name="A", email="a@b.ru", consent=True, now=NOW)
    f.append(pe.publish(b, eid, now=NOW))
    b = pe.replay(f)
    with pytest.raises(ValueError):
        pe.register(b, slug=slug, name="A", email="a@b.ru", consent=False, now=NOW)
    fact, token = pe.register(b, slug=slug, name="A", email="A@b.ru ", consent=True, now=NOW)
    assert token and token not in str(fact)
    f.append(fact)
    b = pe.replay(f)
    assert pe.register(b, slug=slug, name="A", email="a@b.ru", consent=True, now=NOW) == (None, None)
    out = pe.cancel_registration_by_token(b, token)
    assert out[1]["registration_ids"] == [fact["registration_id"]]
    f += out
    b = pe.replay(f)
    with pytest.raises(pe.EventUnavailable):
        pe.register(b, slug=slug, name="A", email="a@b.ru", consent=True, now=NOW)
    with pytest.raises(pe.EventUnavailable):
        pe.cancel_registration_by_token(b, token)
    c = pe.cancel(b, eid)
    f += c
    with pytest.raises(pe.EventUnavailable):
        pe.cancel(pe.replay(f), eid)


def test_validation():
    with pytest.raises(ValueError):
        pe.create_event(title="x", starts_at=NOW - timedelta(hours=1), timezone_name="UTC", now=NOW)
    with pytest.raises(ValueError):
        pe.create_event(title="x", starts_at=NOW + timedelta(hours=1), timezone_name="UTC", kind="party", now=NOW)
    with pytest.raises(ValueError):
        pe.create_event(
            title="x", starts_at=NOW + timedelta(hours=1), timezone_name="UTC", join_url="http://x", now=NOW
        )
    f = [pe.create_event(title="x", starts_at=NOW + timedelta(hours=1), timezone_name="UTC", now=NOW)]
    assert f[0]["provider_key"] == "pending"
    j = pe.set_join_target(pe.replay(f), f[0]["event_id"], "https://zoom.us/j/1")
    assert j["provider_key"] == "zoom"
    assert pe.provider_key("mts-link", join_url="https://a") == "mts_link"
    with pytest.raises(pe.EventUnavailable):
        pe.publish(pe.replay(f), f[0]["event_id"], now=NOW + timedelta(hours=2))
