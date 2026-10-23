from datetime import UTC, datetime, timedelta

import pytest

from application.business_flows import ad_spend_guard as g

NOW = datetime(2026, 10, 23, 10, 0, tzinfo=UTC)
TZ = g.report_timezone({g.REPORT_TZ_ENV: "Europe/Moscow"})


def snap(spent=100, at=NOW, **kw):
    base = dict(connection_id="c", external_account_id="acc", external_campaign_id="cmp", currency="RUB",
                spent_today_minor=spent, strategy="manual", captured_at=at)
    base.update(kw)
    return g.Snapshot(**base)


def auth(status="active", **kw):
    base = dict(authorization_id="a1", business_id="b", connection_id="c", external_campaign_id="cmp",
                currency="RUB", hard_cap_minor=1000, daily_cap_minor=500, expires_at=NOW + timedelta(days=1),
                status=status, consent=snap(spent=100, at=NOW - timedelta(hours=1)))
    base.update(kw)
    return g.Authorization(**base)


def test_timezone_required_fail_closed():
    with pytest.raises(g.SpendInvariantViolation):
        g.report_timezone({})


def test_guard_allows_then_caps():
    assert g.runtime_guard(auth(), snap(200), TZ, NOW).allowed
    assert g.runtime_guard(auth(), snap(600), TZ, NOW).reason == "daily_cap"
    assert g.runtime_guard(auth(hard_cap_minor=50), snap(200), TZ, NOW).reason == "hard_cap"
    assert g.runtime_guard(auth(), snap(50), TZ, NOW).reason == "provider_ineligible"  # spend went backwards
    assert g.runtime_guard(auth(), snap(200, at=NOW - timedelta(minutes=5)), TZ, NOW).reason == "snapshot_stale"
    assert g.runtime_guard(auth(status="revoked"), snap(200), TZ, NOW).reason == "revoked"
    assert g.runtime_guard(auth(), snap(200, external_account_id="x"), TZ, NOW).reason == "provider_ineligible"


def test_managed_strategy_must_be_applied_when_active():
    target = g.managed_strategy(1000, 500)
    a = auth(consent=snap(100, at=NOW - timedelta(hours=1), strategy=g.MANAGED_PREFIX + "x"))
    assert not g.runtime_guard(a, snap(200, strategy=g.MANAGED_PREFIX + "x"), TZ, NOW).allowed
    assert g.runtime_guard(a, snap(200, strategy=target), TZ, NOW).allowed


def test_fresh_snapshot_refreshes_once_on_auth_error():
    calls = []

    def read(tok, a, day, now):
        calls.append(tok)
        if tok == "old":
            raise g.ProviderReadError("provider_53")
        return snap(200, report_date=day)

    s, new = g.fresh_snapshot(auth(), account_id="acc", token={"access_token": "old", "refresh_token": "r"},
                              read=read, refresh=lambda t: {"access_token": "new"}, tz=TZ, now=NOW)
    assert calls == ["old", "new"] and new == {"access_token": "new"} and s.spent_today_minor == 200
    with pytest.raises(g.SpendInvariantViolation):
        g.fresh_snapshot(auth(), account_id="other", token={"access_token": "x"}, read=read, refresh=None, tz=TZ, now=NOW)


def test_sweep_fails_closed_into_dry_run_stop_facts():
    def snap_for(a):
        if a.authorization_id == "boom":
            raise g.ProviderReadError("provider_http_500")
        return snap(200)

    auths = [auth(), auth(authorization_id="boom"), auth(authorization_id="exp", expires_at=NOW), auth(status="draft")]
    r = g.sweep(auths, snap_for, tz=TZ, now=NOW)
    assert (r.scanned, r.allowed, r.stops_queued, r.failed_closed) == (3, 1, 2, 1)
    assert {f["reason"] for f in r.facts} == {"provider_guard_provider_http_500", "expired"}
    assert all(f["dry_run"] for f in r.facts)
