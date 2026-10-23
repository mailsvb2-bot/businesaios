"""Read-only Yandex Direct campaign diagnostics (port of donor yandex_campaign_diagnostics).

Campaigns come only from this tenant's own ad_publication_jobs ledger (CampaignId is
known before an AdId exists, so no submitted ad is required). Metrics come from an
injected read-only provider via ``ad_publication_jobs.Session`` (one refresh on auth
errors). Provider diagnostics only: never business attribution, never spend, and money
is never summed across connections (currency identity unknown).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime

from application.business_flows.ad_publication_jobs import DirectError, Ledger
from application.business_flows.yandex_growth import ReportRow, current_period, percent, unit_cost

CANON_YANDEX_CAMPAIGN_DIAGNOSTICS = True
REPORT_CAMPAIGN_BATCH_SIZE = 500
VISIBLE_JOB_STATUSES = frozenset({"draft", "queued", "publishing", "retry", "submitted", "failed"})


@dataclass(frozen=True, slots=True)
class Tracked:
    connection_id: str
    external_login: str
    campaign_id: str
    campaign_name: str


@dataclass(frozen=True, slots=True)
class DiagnosticsRow:
    connection_id: str
    campaign_id: str
    campaign_name: str
    impressions: int
    clicks: int
    cost_micros: int
    has_provider_row: bool

    @property
    def ctr_percent(self) -> float:
        return percent(self.clicks, self.impressions)

    @property
    def cpc_micros(self) -> int | None:
        return unit_cost(self.cost_micros, self.clicks)


@dataclass(frozen=True, slots=True)
class DiagnosticsSnapshot:
    date_from: str
    date_to: str
    period_days: int
    connected_accounts: int
    managed_campaigns: int
    impressions: int
    clicks: int
    cost_micros: int | None
    campaigns: tuple[DiagnosticsRow, ...]

    @property
    def ctr_percent(self) -> float:
        return percent(self.clicks, self.impressions)

    @property
    def cpc_micros(self) -> int | None:
        return unit_cost(self.cost_micros, self.clicks)


def clean_name(value: object) -> str:
    return " ".join(str(value or "").replace("\x00", " ").split())[:255] or "Без названия"


def _campaign_id(raw: object) -> str:
    cid = str(raw or "").strip()
    if not cid.isdigit() or int(cid) <= 0:
        raise ValueError("external campaign id must be a positive integer")
    return cid


def load_managed_campaigns(led: Ledger, connections: Mapping[str, Mapping[str, object]]) -> tuple[int, list[Tracked]]:
    """Active yandex_direct connections + campaigns referenced by visible jobs (latest job wins the name)."""
    active = {k: c for k, c in connections.items()
              if c.get("status") == "active" and c.get("provider", "yandex_direct") == "yandex_direct"}
    names = {m.external_campaign_id: m.name for m in led.managed.values() if m.external_campaign_id}
    seen: dict[tuple[str, str], Tracked] = {}
    for j in reversed(list(led.jobs.values())):
        if j.connection_id not in active or not str(j.external_campaign_id or "").strip():
            continue
        if str(j.status or "").strip().lower() not in VISIBLE_JOB_STATUSES:
            continue
        camp = _campaign_id(j.external_campaign_id)
        seen.setdefault((j.connection_id, camp), Tracked(
            j.connection_id, str(active[j.connection_id].get("external_login") or ""), camp,
            clean_name(names.get(camp) or j.title)))
    return len(active), [seen[k] for k in sorted(seen, key=lambda k: (k[0], int(k[1])))]


def campaign_batches(ids: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    return tuple(ids[i : i + REPORT_CAMPAIGN_BATCH_SIZE] for i in range(0, len(ids), REPORT_CAMPAIGN_BATCH_SIZE))


def provider_rows(tracked: list[Tracked], *, session_for, date_from: str, date_to: str) -> dict[tuple[str, str], ReportRow]:
    by_conn: dict[str, list[Tracked]] = defaultdict(list)
    for t in tracked:
        by_conn[t.connection_id].append(t)
    rows: dict[tuple[str, str], ReportRow] = {}
    for cid, items in by_conn.items():
        sess = session_for(cid)
        login = items[0].external_login
        for batch in campaign_batches(tuple(sorted({t.campaign_id for t in items}, key=int))):
            report = sess.call(lambda tok, b=batch, s=sess: s.provider.campaign_performance_report(
                tok, b, date_from, date_to, login))
            expected = set(batch)
            for row in report:
                if row.campaign_id not in expected:
                    raise DirectError("analytics_report_campaign_mismatch")
                if (cid, row.campaign_id) in rows:
                    raise DirectError("analytics_report_campaign_duplicate")
                rows[(cid, row.campaign_id)] = row
    return rows


def diagnostics(led: Ledger, *, connections: Mapping[str, Mapping[str, object]], session_for,
                period_days: int = 30, now: datetime | date | None = None,
                env: Mapping[str, str] | None = None) -> DiagnosticsSnapshot:
    date_from, date_to = current_period(period_days, now, env)
    accounts, tracked = load_managed_campaigns(led, connections)
    if not tracked:
        return DiagnosticsSnapshot(date_from, date_to, int(period_days), accounts, 0, 0, 0, 0, ())
    rows = provider_rows(tracked, session_for=session_for, date_from=date_from, date_to=date_to)
    camps = []
    for t in tracked:
        r = rows.get((t.connection_id, t.campaign_id))
        camps.append(DiagnosticsRow(t.connection_id, t.campaign_id, r.campaign_name if r else t.campaign_name,
                                    r.impressions if r else 0, r.clicks if r else 0, r.cost_micros if r else 0,
                                    r is not None))
    cost = sum(c.cost_micros for c in camps) if len({t.connection_id for t in tracked}) <= 1 else None
    return DiagnosticsSnapshot(date_from, date_to, int(period_days), accounts, len(camps),
                               sum(c.impressions for c in camps), sum(c.clicks for c in camps), cost, tuple(camps))


__all__ = [
    "CANON_YANDEX_CAMPAIGN_DIAGNOSTICS", "DiagnosticsRow", "DiagnosticsSnapshot", "Tracked", "campaign_batches",
    "clean_name", "diagnostics", "load_managed_campaigns", "provider_rows",
]
