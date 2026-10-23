from datetime import date

import pytest

from application.business_flows import yandex_campaign_diagnostics as yd
from application.business_flows.ad_publication_jobs import DirectError, Job, Ledger, Session
from application.business_flows.yandex_growth import ReportRow


def _job(jid, conn, camp, status="submitted", title="T"):
    return Job(jid, "p1", conn, camp, (213,), title, "x", "https://e.ru", status=status)


class _Prov:
    def __init__(self, rows, fail_once=False):
        self.rows, self.fail_once, self.calls = rows, fail_once, []

    def refresh(self, token):
        return {**token, "access_token": "new"}

    def campaign_performance_report(self, tok, ids, d1, d2, login):
        self.calls.append((tok, ids, login))
        if self.fail_once:
            self.fail_once = False
            raise DirectError("provider_http_401")
        return [r for r in self.rows if r.campaign_id in ids]


def test_diagnostics_single_connection_sums_cost_and_refreshes_once():
    led = Ledger()
    led.jobs = {"a": _job("a", "c1", "11"), "b": _job("b", "c1", "12", status="failed"),
                "z": _job("z", "c1", "13", status="cancelled")}
    prov = _Prov([ReportRow("", "11", "Camp", 100, 5, 5_000_000)], fail_once=True)
    sess = Session(prov, {"access_token": "old", "refresh_token": "env:R"})
    snap = yd.diagnostics(led, connections={"c1": {"status": "active", "external_login": "lg"}},
                          session_for=lambda c: sess, period_days=7, now=date(2026, 10, 20))
    assert (snap.date_from, snap.managed_campaigns, snap.cost_micros) == ("2026-10-14", 2, 5_000_000)
    assert [c.has_provider_row for c in snap.campaigns] == [True, False]
    assert snap.campaigns[0].cpc_micros == 1_000_000 and snap.ctr_percent == 5.0
    assert [c[0] for c in prov.calls] == ["old", "new"]


def test_cost_not_summed_across_connections_and_mismatch_rejected():
    led = Ledger()
    led.jobs = {"a": _job("a", "c1", "11"), "b": _job("b", "c2", "21")}
    conns = {"c1": {"status": "active"}, "c2": {"status": "active"}}
    ok = _Prov([ReportRow("", "11", "", 1, 1, 10), ReportRow("", "21", "", 1, 1, 10)])
    snap = yd.diagnostics(led, connections=conns, session_for=lambda c: Session(ok, {"access_token": "t"}), period_days=30)
    assert snap.cost_micros is None and snap.clicks == 2

    class Bad(_Prov):
        def campaign_performance_report(self, *a):
            return [ReportRow("", "99")]
    with pytest.raises(DirectError):
        yd.diagnostics(led, connections=conns, session_for=lambda c: Session(Bad([]), {"access_token": "t"}))


def test_empty_and_helpers():
    snap = yd.diagnostics(Ledger(), connections={"c1": {"status": "active"}}, session_for=None, now=date(2026, 1, 30))
    assert snap.connected_accounts == 1 and snap.campaigns == () and snap.cpc_micros is None
    assert yd.clean_name(" a\x00  b ") == "a b" and yd.clean_name("") == "Без названия"
    assert len(yd.campaign_batches(tuple(str(i) for i in range(1, 1002)))) == 3
