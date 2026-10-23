from datetime import date

import pytest

from application.business_flows import ad_publication_jobs as aj
from application.business_flows import yandex_growth as yg


class Rep(aj.DryRunDirectProvider):
    def __init__(self, rows, fail_first=False):
        super().__init__()
        self.rows, self.fail_first = rows, fail_first

    def performance_report(self, token, ad_ids, date_from, date_to, login):
        if self.fail_first and token == "t":
            raise aj.DirectError("provider_53")
        return [r for r in self.rows if r.ad_id in ad_ids]


def ledger():
    led = aj.Ledger()
    for i, (cid, camp) in enumerate([("c1", "10"), ("c1", "10"), ("c2", "20")], start=1):
        led.jobs[f"j{i}"] = aj.Job(f"j{i}", f"p{i}", cid, camp, (1,), "T", "X", "u", status="submitted", ad_id=str(i))
    led.jobs["q"] = aj.Job("q", "p9", "c1", "10", (1,), "T", "X", "u")
    return led


CONN = {"c1": {"status": "active", "external_login": "a"}, "c2": {"status": "active", "external_login": "b"}}
ROWS = [yg.ReportRow("1", "10", "Camp", 100, 10, 1000), yg.ReportRow("2", "10", "", 100, 0, 0),
        yg.ReportRow("3", "20", "B", 50, 5, 500)]


def test_snapshot_multi_currency_safe_and_attribution():
    attr = yg.Attribution(leads={"p1": frozenset({"L1"}), "p2": frozenset({"L1", "L2"})}, won={"p3": frozenset({"W"})})
    s = yg.growth_snapshot(ledger(), connections=CONN, session_for=lambda c: aj.Session(Rep(ROWS, True), {"access_token": "t", "refresh_token": "r"}),
                           attribution=attr, period_days=7, now=date(2026, 10, 23), env={})
    assert (s.date_from, s.date_to) == ("2026-10-17", "2026-10-23")
    assert s.tracked_ads == 3 and s.impressions == 250 and s.cost_micros is None and s.cpc_micros is None
    assert s.leads == 2 and s.won == 1
    top = s.campaigns[0]
    assert top.campaign_name == "Camp" and top.cost_micros == 1000 and top.cpc_micros == 100 and top.cpl_micros == 500
    assert top.ctr_percent == 5.0


def test_guards():
    with pytest.raises(ValueError):
        yg.current_period(14)
    with pytest.raises(RuntimeError):
        yg.report_zone({"YANDEX_DIRECT_REPORT_TIMEZONE": "Nope/Zone"})
    bad = [yg.ReportRow("1", "99")]
    with pytest.raises(aj.DirectError, match="mismatch"):
        yg.growth_snapshot(ledger(), connections=CONN, session_for=lambda c: aj.Session(Rep(bad), {"access_token": "t"}),
                           attribution=yg.Attribution(), env={})
    empty = yg.growth_snapshot(aj.Ledger(), connections=CONN, session_for=None, attribution=yg.Attribution(), env={})
    assert empty.tracked_ads == 0 and empty.connected_accounts == 2
    assert len(yg.ad_id_batches(tuple(str(i) for i in range(1001)))) == 3
