from datetime import UTC, datetime, timedelta

import pytest

from application.business_flows import event_owner_flow as of
from application.business_flows import public_events as pe

NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)
SMTP = {"id": "c1", "platform": "email", "type": "email_smtp", "status": "active", "created_at": "1"}


def test_notification_connection():
    assert of.notification_connection([SMTP], requested=None, enabled=False) is None
    assert of.notification_connection([SMTP], requested=None, enabled=True) == "c1"
    assert of.notification_connection([], requested=None, enabled=True) is None
    with pytest.raises(ValueError):
        of.notification_connection([SMTP, {**SMTP, "id": "c2"}], requested=None, enabled=True)
    with pytest.raises(ValueError):
        of.notification_connection([SMTP], requested="zz", enabled=True)


def test_single_and_multisession():
    f = of.create_and_publish(title="Вебинар", starts_at=NOW + timedelta(days=1), timezone_name="Europe/Moscow",
                              now=NOW, connections=[SMTP])
    assert pe.replay(f).events[f[0]["event_id"]].status == "published" and f[0]["notification_connection_id"] == "c1"
    s1 = of.SessionSpec(NOW + timedelta(days=2), join_url="https://zoom.us/j/1")
    f = of.create_draft(title="Курс", timezone_name="Europe/Moscow", sessions=[s1], now=NOW, connections=[])
    eid = f[0]["event_id"]
    f.append(of.append_session(f, eid, of.SessionSpec(NOW + timedelta(days=3))))
    assert len(of.sessions_of(f, eid)) == 2 and not of.join_ready(f, eid)
    f.append(of.publish_draft(f, eid, now=NOW))
    with pytest.raises(pe.EventUnavailable):
        of.append_session(f, eid, s1)
    with pytest.raises(ValueError):
        of.create_draft(title="X", timezone_name="UTC", sessions=[], now=NOW, connections=[])
    g = of.create_and_publish_multisession(title="Y", timezone_name="UTC", sessions=[s1], now=NOW, connections=[])
    assert g[-1]["status"] == "published" and of.join_ready(g, g[0]["event_id"])
    assert of.registration_url("https://x.ru/", "abc") == "https://x.ru/e/abc"


def test_sessions_helpers():
    s = [of.SessionSpec(NOW + timedelta(days=2), ends_at=NOW + timedelta(days=2, hours=1)),
         of.SessionSpec(NOW + timedelta(days=3))]
    f = of.create_draft(title="Z", timezone_name="Europe/Moscow", sessions=s[:1], now=NOW, connections=[])
    eid = f[0]["event_id"]
    with pytest.raises(ValueError):
        of.configure_sessions(f, eid, [of.SessionSpec(NOW)], now=NOW)
    f.append(of.configure_sessions(f, eid, s, now=NOW, reschedule_notifications=True))
    ss = of.sessions_of(f, eid)
    assert of.warmup_window(ss, timezone_name="Europe/Moscow", now=NOW) == 2
    assert of.validate_warmup_days(2, max_days=2) == 2
    for bad in (3, -1, True):
        with pytest.raises(ValueError):
            of.validate_warmup_days(bad, max_days=2)
    assert of.select_for_join(ss, now=NOW) == ss[0]
    assert of.select_for_join(ss, now=NOW + timedelta(days=2, hours=2)) == ss[1]
    assert of.select_for_join(ss, now=NOW + timedelta(days=9)) == ss[1]
    assert of.select_for_join(ss, position=2, now=NOW) == ss[1]
    with pytest.raises(LookupError):
        of.select_for_join(ss, position=3, now=NOW)
    f.append(of.set_session_join(f, eid, 2, "https://telemost.yandex.ru/j/2"))
    assert of.sessions_of(f, eid)[1]["provider_key"] == "yandex_telemost"
