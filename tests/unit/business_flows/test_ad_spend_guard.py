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


def test_consent_lifecycle_binds_terms_and_snapshot():
    a = auth(status="prepared")
    log = [g.request_consent([], a, NOW)]
    with pytest.raises(g.SpendInvariantViolation):
        g.request_consent(log, a, NOW)
    with pytest.raises(g.SpendInvariantViolation, match="terms"):
        g.grant_consent(log, a, expected_terms_hash="x", expected_snapshot_hash=log[0]["snapshot_hash"],
                        receipt_id="r", now=NOW)
    with pytest.raises(g.SpendInvariantViolation, match="snapshot"):
        g.grant_consent(log, a, expected_terms_hash=log[0]["terms_hash"], expected_snapshot_hash="x",
                        receipt_id="r", now=NOW)
    log.append(g.grant_consent(log, a, expected_terms_hash=log[0]["terms_hash"],
                               expected_snapshot_hash=log[0]["snapshot_hash"], receipt_id="r", now=NOW))
    assert g.consent_status(log, a) == "authorized"
    assert g.consent_view(log, [a])[0]["status"] == "authorized"
    with pytest.raises(g.SpendInvariantViolation, match="disabled"):
        g.queue_operation(log, a, "launch", env={})
    op = g.queue_operation(log, a, "launch", env={g.MUTATIONS_ENV: "1"}, now=NOW)
    assert op["step"] == "ad_spend_launch_queued" and op["dry_run"] is True
    rv = g.revoke_consent(log, a, actor_member_id="m", now=NOW)
    assert [f["step"] for f in rv] == ["ad_spend_consent_revoked"]
    assert g.revoke_consent(log + rv, a, actor_member_id="m") == []
    with pytest.raises(g.SpendInvariantViolation):
        g.queue_operation(log + rv, a, "launch", env={g.MUTATIONS_ENV: "1"})


def test_revoke_live_queues_dry_run_stop_and_evidence():
    a = auth(status="active")
    rv = g.revoke_consent([], a, actor_member_id="m", now=NOW)
    assert rv[1]["step"] == "ad_spend_stop_queued" and rv[1]["dry_run"] is True
    assert g.queue_operation([], a, "stop", env={})["step"] == "ad_spend_stop_queued"
    ev = g.superseded_evidence(None, g.ProviderReadError("provider_53"))
    assert ev["provider_error_code"] == "provider_53" and ev["provider_outcome_unknown"] is True
    assert g.superseded_evidence({"k": 1}, ValueError()) == {"k": 1}


# --- provider port / preparation / goal caps / operation queue (fakes only, no network, no spend) ---
ENV = {g.CEILING_ENV: "5000", g.MUTATIONS_ENV: "1", g.PROVIDER_ENV: "1", g.REPORT_TZ_ENV: "Europe/Moscow"}
BUNDLE = {"access_token": "t0", "refresh_token": "r0"}


class FakeProvider(g.AdProviderPort):
    def __init__(self, spent=100, minimum=7_000_000, fail_reads=(), mutate_error=None):
        self.calls, self.spent, self.minimum = [], spent, minimum
        self.fail_reads, self.mutate_error = list(fail_reads), mutate_error

    def read_budget(self, access_token, *, campaign_id, report_date, now):
        self.calls.append(("read", access_token))
        if self.fail_reads:
            raise g.ProviderReadError(self.fail_reads.pop(0))
        return g.BudgetReadout("acc", campaign_id, "RUB", 3000, self.spent, "manual", report_date, self.minimum)

    def refresh(self, bundle):
        self.calls.append(("refresh", bundle["refresh_token"]))
        return {"access_token": "t1", "refresh_token": "r1"}

    def _m(self, name, **kw):
        self.calls.append((name, kw["idempotency_key"]))
        if self.mutate_error:
            raise g.ProviderReadError(self.mutate_error)
        return {"ok": True}

    def configure_budget(self, access_token, **kw):
        return self._m("configure_budget", **kw)

    def moderate_ad(self, access_token, **kw):
        return self._m("moderate_ad", **kw)

    def suspend_ad(self, access_token, **kw):
        return self._m("suspend_ad", **kw)


def prepared(provider=None, hard=1000, daily=500, env=ENV, **kw):
    a, fact = g.prepare_authorization(
        provider or FakeProvider(), BUNDLE, business_id="b", connection_id="c", external_account_id="acc",
        external_campaign_id="cmp", hard_cap_minor=hard, daily_cap_minor=daily, expires_at=NOW + timedelta(seconds=240),
        report_date="2026-10-23", tz=TZ, now=NOW, env=env, **kw)
    return a, fact


def test_prepare_authorization_validates_everything_and_spends_nothing():
    p = FakeProvider()
    a, fact = prepared(p)
    assert a.status == "prepared" and fact["ttl_seconds"] == 240 and p.calls == [("read", "t0")]
    assert g.authorizations_replay([fact, fact])[a.authorization_id].hard_cap_minor == 1000
    bad = [dict(hard=1000, daily=500, env={}), dict(hard=6000, daily=500), dict(hard=1000, daily=2000),
           dict(hard=3500, daily=500, env={**ENV, g.CEILING_ENV: "9000"})]  # last: above available budget 3000
    for kw in bad:
        with pytest.raises(g.SpendInvariantViolation):
            prepared(FakeProvider(), **kw)
    with pytest.raises(g.SpendInvariantViolation):  # below the provider minimum weekly budget
        prepared(FakeProvider(minimum=11_000_000))
    for expires in (NOW, NOW + timedelta(seconds=301), NOW.replace(tzinfo=None)):
        with pytest.raises((g.SpendInvariantViolation, ValueError)):
            g.prepare_authorization(FakeProvider(), BUNDLE, business_id="b", connection_id="c", external_account_id="acc",
                                    external_campaign_id="cmp", hard_cap_minor=1000, daily_cap_minor=500, expires_at=expires,
                                    report_date="2026-10-23", tz=TZ, now=NOW, env=ENV)
    for day in ("2026-10-20", "23.10.2026", NOW):
        with pytest.raises((g.SpendInvariantViolation, ValueError)):
            g.check_report_date(day, now=NOW)
    assert g.check_report_date("2026-10-24", now=NOW) == "2026-10-24"
    with pytest.raises(g.SpendInvariantViolation):  # another account behind the same connection
        g.prepare_authorization(FakeProvider(), BUNDLE, business_id="b", connection_id="c", external_account_id="other",
                                external_campaign_id="cmp", hard_cap_minor=1000, daily_cap_minor=500,
                                expires_at=NOW + timedelta(seconds=60), report_date="2026-10-23", tz=TZ, now=NOW, env=ENV)


def test_prepare_refreshes_once_then_gives_up():
    p = FakeProvider(fail_reads=["provider_53"])
    prepared(p, refresh=lambda b: g.refresh_bundle(p, b))
    assert [c[0] for c in p.calls] == ["read", "refresh", "read"]
    p2 = FakeProvider(fail_reads=["provider_53", "provider_53"])
    with pytest.raises(g.ProviderReadError):
        prepared(p2, refresh=lambda b: g.refresh_bundle(p2, b))
    assert [c[0] for c in p2.calls].count("refresh") == 1
    p3 = FakeProvider(fail_reads=["provider_500"])
    with pytest.raises(g.ProviderReadError):
        prepared(p3, refresh=lambda b: g.refresh_bundle(p3, b))
    assert [c[0] for c in p3.calls] == ["read"]


def test_goal_caps_and_preview():
    assert g.goal_caps(30_000, minimum_weekly_micros=7_000_000, env={}) == (10_000, 10_000)
    assert g.goal_caps(30_000, minimum_weekly_micros=7_000_000, env={g.GOAL_MAX_ENV: "2000", g.GOAL_DAILY_ENV: "500"}) == (2000, 500)
    for env, avail in (({g.GOAL_MAX_ENV: "100"}, 30_000), ({}, 500), ({g.GOAL_DAILY_ENV: "10"}, 30_000), ({g.GOAL_MAX_ENV: "abc"}, 30_000)):
        with pytest.raises((g.SpendInvariantViolation, RuntimeError)):
            g.goal_caps(avail, minimum_weekly_micros=7_000_000, env=env)
    with pytest.raises(g.SpendInvariantViolation):
        g.minimum_weekly_minor(7_000_001)
    p = FakeProvider()
    pv = g.preview_goal_spend(p, BUNDLE, connection_id="c", campaign_id="cmp", now=NOW, tz=TZ, env={**ENV})
    assert (pv.recommended_hard_cap_minor, pv.recommended_daily_cap_minor) == (3000, 3000) and p.calls == [("read", "t0")]
    with pytest.raises(g.SpendInvariantViolation):  # ceiling not configured: no preview of spendable caps
        g.preview_goal_spend(FakeProvider(), BUNDLE, connection_id="c", campaign_id="cmp", now=NOW, tz=TZ, env={})


def test_secret_refs_only_and_dry_run_provider():
    for raw in ("sk-live-123", "env:A/B", "", "vault:"):
        with pytest.raises(ValueError):
            g.secret_ref(raw)
    v = g.ad_vault(lambda ref: '{"access_token":"a","refresh_token":"r"}' if ref == "vault:YD" else None)
    assert g.load_bundle(v, "vault:YD")["access_token"] == "a"
    with pytest.raises(g.ProviderReadError):
        g.load_bundle(v, "vault:OTHER")
    with pytest.raises(ValueError):
        g.load_bundle(v, "raw-token")
    env = {g.CONNECTIONS_ENV: "1", "YANDEX_DIRECT_CLIENT_ID": "cid", "YANDEX_DIRECT_CLIENT_SECRET_REF": "env:YD_SECRET",
           "BAI_DOMAIN": "bai.example"}
    assert isinstance(g.yandex_provider(FakeProvider, env), g.DryRunAdProvider)  # provider flag off
    assert isinstance(g.yandex_provider(FakeProvider, {**env, g.PROVIDER_ENV: "1"}), FakeProvider)
    for broken in ({**env, g.CONNECTIONS_ENV: ""}, {**env, "YANDEX_DIRECT_CLIENT_SECRET_REF": "rawsecret"},
                   {**env, "YANDEX_DIRECT_CLIENT_ID": ""}, {k: v for k, v in env.items() if k != "BAI_DOMAIN"}):
        with pytest.raises((RuntimeError, ValueError)):
            g.yandex_provider(FakeProvider, broken)
    assert g.redirect_uri(env).endswith("/oauth/yandex-direct/callback")
    with pytest.raises(g.ProviderReadError):
        g.DryRunAdProvider().read_budget("t", campaign_id="c", report_date="d", now=NOW)
    assert g.DryRunAdProvider().configure_budget("t")["dry_run"] is True


def _authorized(provider=None):
    a, fact = prepared(provider)
    pay = [fact, g.request_consent([fact], a, NOW)]
    pay.append(g.grant_consent(pay, a, expected_terms_hash=g.terms_hash(a), expected_snapshot_hash=g.snapshot_hash(a.consent),
                               receipt_id="rcpt-1", now=NOW))
    return a, pay


def test_launch_is_dry_run_without_flag_and_idempotent_with_it():
    a, pay = _authorized()
    off = g.launch_or_dry_run(pay, a, env={**ENV, g.MUTATIONS_ENV: ""}, now=NOW)
    assert off["step"] == "ad_spend_launch_dry_run" and g.consent_status(pay + [off], a) == "authorized"
    with pytest.raises(g.SpendInvariantViolation):  # no ceiling -> impossible even with the flag
        g.launch_or_dry_run(pay, a, env={g.MUTATIONS_ENV: "1"}, now=NOW)
    on = g.launch_or_dry_run(pay, a, env=ENV, now=NOW)
    pay.append(on)
    assert on["step"] == "ad_spend_launch_queued" and g.consent_status(pay, a) == "launching"
    with pytest.raises(g.SpendInvariantViolation):  # a second launch is refused: no double spend
        g.launch_or_dry_run(pay, a, env=ENV, now=NOW)
    assert list(g.ops_replay(pay + [on])) == [g.op_id(a.authorization_id, "launch")]


def test_process_launch_configures_budget_once_with_idempotency_keys():
    p = FakeProvider()
    a, pay = _authorized(p)
    pay.append(g.launch_or_dry_run(pay, a, env=ENV, now=NOW))
    p.calls.clear()
    facts = g.process_one_operation(pay, p, BUNDLE, tz=TZ, env=ENV, now=NOW)
    oid = g.op_id(a.authorization_id, "launch")
    assert [f["step"] for f in facts] == ["ad_spend_op_claimed", "ad_spend_op_completed", "ad_spend_launched"]
    assert ("configure_budget", f"{oid}:budget") in p.calls and ("moderate_ad", f"{oid}:moderate") in p.calls
    pay += facts
    assert g.consent_status(pay, a) == "active"
    p.calls.clear()
    assert g.process_one_operation(pay, p, BUNDLE, tz=TZ, env=ENV, now=NOW) == [] and p.calls == []  # nothing due, no re-spend


def test_process_blocks_on_guard_ceiling_and_expiry():
    p = FakeProvider(spent=900)  # snapshot spend jumps past the daily cap between consent and launch
    a, pay = _authorized(FakeProvider())
    pay.append(g.launch_or_dry_run(pay, a, env=ENV, now=NOW))
    p.spent = 900
    facts = g.process_one_operation(pay, p, BUNDLE, tz=TZ, env=ENV, now=NOW)
    assert facts[1]["code"] == "guard_daily_cap" and facts[-1]["step"] == "ad_spend_launch_failed"
    assert not [c for c in p.calls if c[0] in {"configure_budget", "moderate_ad"}]
    a, pay = _authorized()
    pay.append(g.launch_or_dry_run(pay, a, env=ENV, now=NOW))
    late = g.process_one_operation(pay, FakeProvider(), BUNDLE, tz=TZ, env=ENV, now=NOW + timedelta(seconds=241))
    assert late[1]["code"].startswith("spendinvariantviolation") and not late[1]["retryable"]
    noceil = g.process_one_operation(pay, FakeProvider(), BUNDLE, tz=TZ, env={g.MUTATIONS_ENV: "1"}, now=NOW)
    assert "CEILING" in noceil[1]["code"]


def test_process_retry_backoff_dead_letter_and_stale_lease_recovery():
    p = FakeProvider(mutate_error="provider_503")
    a, pay = _authorized(p)
    pay.append(g.launch_or_dry_run(pay, a, env=ENV, now=NOW))
    f1 = g.process_one_operation(pay, p, BUNDLE, tz=TZ, env=ENV, now=NOW)
    assert f1[1]["retryable"] is True and f1[1]["outcome_unknown"] is True and len(f1) == 2
    pay += f1
    assert g.process_one_operation(pay, p, BUNDLE, tz=TZ, env=ENV, now=NOW + timedelta(seconds=30)) == []  # backoff
    f2 = g.process_one_operation(pay, p, BUNDLE, tz=TZ, env=ENV, now=NOW + timedelta(seconds=61))
    assert f2[0]["attempt"] == 2
    pay += f2
    # past the authorization expiry a retry becomes terminal: the launch is dead-lettered and marked failed
    f3 = g.process_one_operation(pay, p, BUNDLE, tz=TZ, env=ENV, now=NOW + timedelta(seconds=260))
    pay += f3
    assert f3[-1]["step"] == "ad_spend_launch_failed" and g.consent_status(pay, a) == "failed"
    assert g.ops_replay(pay)[g.op_id(a.authorization_id, "launch")].state == "dead"
    # a stop has no expiry: after MAX_ATTEMPTS provider failures it is dead-lettered
    a, pay = _authorized(p)
    pay.append(g.launch_or_dry_run(pay, a, env=ENV, now=NOW))
    pay.append(g.queue_operation(pay, a, "stop", env=ENV, now=NOW))
    pay += g.process_one_operation(pay, p, BUNDLE, tz=TZ, env=ENV, now=NOW)  # launch superseded
    t = NOW
    for n in range(1, g.MAX_ATTEMPTS + 1):
        t += timedelta(hours=2)
        f = g.process_one_operation(pay, p, BUNDLE, tz=TZ, env=ENV, now=t)
        assert f[0]["attempt"] == n and f[1]["step"] == "ad_spend_op_failed"
        pay += f
    assert g.ops_replay(pay)[g.op_id(a.authorization_id, "stop")].state == "dead"
    assert g.process_one_operation(pay, p, BUNDLE, tz=TZ, env=ENV, now=t + timedelta(days=1)) == []
    # crash recovery: a claimed op whose lease expired is re-claimed, a live lease is not
    a, pay = _authorized(FakeProvider())
    pay.append(g.launch_or_dry_run(pay, a, env=ENV, now=NOW))
    claim = g.process_one_operation(pay, FakeProvider(spent=900), BUNDLE, tz=TZ, env=ENV, now=NOW)[0]
    crashed = pay + [claim]
    assert g.process_one_operation(crashed, FakeProvider(), BUNDLE, tz=TZ, env=ENV, now=NOW + timedelta(seconds=30)) == []
    again = g.process_one_operation(crashed, FakeProvider(), BUNDLE, tz=TZ, env=ENV, now=NOW + timedelta(seconds=61))
    assert again[0]["recovered_stale_lease"] is True and again[0]["attempt"] == 2


def test_stop_supersedes_launch_and_dry_run_provider_never_marks_launched():
    p = FakeProvider()
    a, pay = _authorized(p)
    pay.append(g.launch_or_dry_run(pay, a, env=ENV, now=NOW))
    pay.append(g.queue_operation(pay, with_s := g.with_status(pay, a), "stop", env=ENV, now=NOW))
    assert with_s.status == "launching"
    p.calls.clear()
    f = g.process_one_operation(pay, p, BUNDLE, tz=TZ, env=ENV, now=NOW)
    assert f[0]["op_id"] == g.op_id(a.authorization_id, "launch") and f[1]["evidence"]["superseded"] is True and p.calls == []
    pay += f
    f2 = g.process_one_operation(pay, p, BUNDLE, tz=TZ, env=ENV, now=NOW)
    assert ("suspend_ad", g.op_id(a.authorization_id, "stop") + ":suspend") in p.calls
    assert f2[-1]["step"] == "ad_spend_stopped"
    # provider flag off (dry-run provider): reads fail closed, nothing external, launch ends failed not active
    a, pay = _authorized()
    pay.append(g.launch_or_dry_run(pay, a, env=ENV, now=NOW))
    f3 = g.process_one_operation(pay, g.DryRunAdProvider(), BUNDLE, tz=TZ, env=ENV, now=NOW)
    assert f3[1]["code"] == "provider_dry_run" and "ad_spend_launched" not in [x["step"] for x in f3]
