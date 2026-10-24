"""Read-only Yandex Direct growth snapshot (port of donor yandex_growth_analytics).

Inputs are the ad_publication_jobs ledger (submitted ads), active connections,
local promotion attribution and an injected read-only report provider used via
``ad_publication_jobs.Session`` (refresh once on auth errors). Never spends.
Costs are never summed across connections (currency identity unknown).
"""

from __future__ import annotations

import os
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from application.business_flows.ad_publication_jobs import DirectError, Ledger, Session

ALLOWED_PERIOD_DAYS = frozenset({7, 30})
REPORT_AD_BATCH_SIZE = 500


@dataclass(frozen=True, slots=True)
class ReportRow:
    ad_id: str
    campaign_id: str
    campaign_name: str = ""
    impressions: int = 0
    clicks: int = 0
    cost_micros: int = 0


@dataclass(frozen=True, slots=True)
class Attribution:
    leads: Mapping[str, frozenset[str]] = field(default_factory=dict)
    bookings: Mapping[str, frozenset[str]] = field(default_factory=dict)
    won: Mapping[str, frozenset[str]] = field(default_factory=dict)


def percent(num: int, den: int) -> float:
    return 0.0 if den <= 0 else round(int(num) / int(den) * 100.0, 1)


def unit_cost(cost: int | None, n: int) -> int | None:
    return None if cost is None or n <= 0 else int(cost) // int(n)


class _Units:
    cost_micros: int | None
    clicks: int
    impressions: int
    leads: int
    bookings: int
    won: int

    @property
    def ctr_percent(self) -> float:
        return percent(self.clicks, self.impressions)

    @property
    def cpc_micros(self) -> int | None:
        return unit_cost(self.cost_micros, self.clicks)

    @property
    def cpl_micros(self) -> int | None:
        return unit_cost(self.cost_micros, self.leads)

    @property
    def booking_cost_micros(self) -> int | None:
        return unit_cost(self.cost_micros, self.bookings)

    @property
    def cac_micros(self) -> int | None:
        return unit_cost(self.cost_micros, self.won)


@dataclass(frozen=True)
class GrowthCampaign(_Units):
    connection_id: str
    campaign_id: str
    campaign_name: str
    tracked_ads: int
    impressions: int
    clicks: int
    cost_micros: int | None
    leads: int
    bookings: int
    won: int


@dataclass(frozen=True)
class GrowthSnapshot(_Units):
    date_from: str
    date_to: str
    period_days: int
    connected_accounts: int
    tracked_ads: int
    impressions: int
    clicks: int
    cost_micros: int | None
    leads: int
    bookings: int
    won: int
    campaigns: tuple[GrowthCampaign, ...]


def report_zone(env: Mapping[str, str] | None = None) -> ZoneInfo:
    name = ((os.environ if env is None else env).get("YANDEX_DIRECT_REPORT_TIMEZONE") or "Europe/Moscow").strip()
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise RuntimeError("Yandex Direct report timezone is invalid") from exc


def current_period(days: int, now: datetime | date | None = None, env: Mapping[str, str] | None = None) -> tuple[str, str]:
    if int(days) not in ALLOWED_PERIOD_DAYS:
        raise ValueError("Yandex analytics period must be 7 or 30 days")
    zone = report_zone(env)
    if isinstance(now, datetime):
        end = now.astimezone(zone).date() if now.utcoffset() is not None else now.date()
    elif isinstance(now, date):
        end = now
    else:
        end = datetime.now(zone).date()
    return (end - timedelta(days=int(days) - 1)).isoformat(), end.isoformat()


def ad_id_batches(ad_ids: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    return tuple(ad_ids[i : i + REPORT_AD_BATCH_SIZE] for i in range(0, len(ad_ids), REPORT_AD_BATCH_SIZE))


def tracked_ads(led: Ledger, connections: Mapping[str, Mapping[str, object]]) -> list:
    """Submitted jobs with an external ad id on an active yandex_direct connection."""
    return [j for j in led.jobs.values() if j.status == "submitted" and j.ad_id
            and (connections.get(j.connection_id) or {}).get("status") == "active"]


def provider_rows(tracked: list, *, connections: Mapping[str, Mapping[str, object]], session_for,
                  date_from: str, date_to: str) -> dict[tuple[str, str], ReportRow]:
    by_conn: dict[str, list] = defaultdict(list)
    for j in tracked:
        by_conn[j.connection_id].append(j)
    rows: dict[tuple[str, str], ReportRow] = {}
    for cid, items in by_conn.items():
        sess: Session = session_for(cid)
        expected = {j.ad_id: j.external_campaign_id for j in items}
        login = str(connections[cid].get("external_login") or "")
        for batch in ad_id_batches(tuple(sorted(expected, key=int))):
            report = sess.call(lambda t, b=batch, s=sess, lg=login: s.provider.performance_report(t, b, date_from, date_to, lg))
            for row in report:
                if expected.get(row.ad_id) is None or row.campaign_id != expected[row.ad_id]:
                    raise DirectError("analytics_report_campaign_mismatch")
                rows[(cid, row.ad_id)] = row
    return rows


def growth_snapshot(led: Ledger, *, connections: Mapping[str, Mapping[str, object]], session_for,
                    attribution: Attribution, period_days: int = 30, now: datetime | date | None = None,
                    env: Mapping[str, str] | None = None) -> GrowthSnapshot:
    date_from, date_to = current_period(period_days, now, env)
    active = sum(1 for c in connections.values() if c.get("status") == "active")
    tracked = tracked_ads(led, connections)
    if not tracked:
        return GrowthSnapshot(date_from, date_to, int(period_days), active, 0, 0, 0, 0, 0, 0, 0, ())
    rows = provider_rows(tracked, connections=connections, session_for=session_for, date_from=date_from, date_to=date_to)
    targets: dict[tuple[str, str], list] = defaultdict(list)
    for j in tracked:
        targets[(j.connection_id, j.external_campaign_id)].append(j)
    camps: list[GrowthCampaign] = []
    all_l: set[str] = set()
    all_b: set[str] = set()
    all_w: set[str] = set()
    for (cid, camp), items in sorted(targets.items(), key=lambda p: (p[0][0], int(p[0][1]))):
        ads = {j.ad_id for j in items}
        prov = [rows[(cid, a)] for a in ads if (cid, a) in rows]
        promos = {j.promotion_id for j in items}
        lead = set().union(*(attribution.leads.get(p, frozenset()) for p in promos))
        book = set().union(*(attribution.bookings.get(p, frozenset()) for p in promos))
        won = set().union(*(attribution.won.get(p, frozenset()) for p in promos))
        all_l |= lead
        all_b |= book
        all_w |= won
        name = next((r.campaign_name for r in prov if r.campaign_name), "")
        camps.append(GrowthCampaign(cid, camp, name, len(ads), sum(r.impressions for r in prov),
                                    sum(r.clicks for r in prov), sum(r.cost_micros for r in prov),
                                    len(lead), len(book), len(won)))
    vals = list(rows.values())
    cost = sum(r.cost_micros for r in vals) if len({j.connection_id for j in tracked}) == 1 else None
    return GrowthSnapshot(date_from, date_to, int(period_days), active,
                          len({(j.connection_id, j.ad_id) for j in tracked}),
                          sum(r.impressions for r in vals), sum(r.clicks for r in vals), cost,
                          len(all_l), len(all_b), len(all_w),
                          tuple(sorted(camps, key=lambda c: (c.cost_micros or 0, c.clicks, c.impressions), reverse=True)))


# --- creative trial allocation (donor creative_growth_optimizer) -------------------------------
# Advisory only: proposes one bounded 10,000-bps reallocation step; never touches provider budget.
CREATIVE_METRICS = ("bookings", "won")


def creative_allocation(
    arms: list[dict[str, object]], *, running: bool, metric: str = "bookings", min_leads_per_arm: int = 30,
    exploration_floor_bps: int = 1_000, max_shift_bps: int = 1_000,
) -> dict[str, object]:
    """arms: {variant_id, publication_job_id, allocation_bps, leads, bookings, won, scope='variant'}.

    status: ready | not_running | attribution_not_ready | insufficient_data | no_clear_winner |
    exploration_floor_reached. Winner must be separated by non-overlapping 95% Wilson intervals.
    """
    from core.experiments.evaluators.live_canary_statistics import wilson_interval

    if metric not in CREATIVE_METRICS:
        raise ValueError("unsupported creative optimization metric")
    if min_leads_per_arm < 1 or not 1 <= exploration_floor_bps < 5_000 or not 1 <= max_shift_bps <= 5_000:
        raise ValueError("creative optimization bounds invalid")
    out: dict[str, object] = {"metric": metric, "winner_variant_id": "", "evidence": []}
    if not running:
        return {**out, "status": "not_running"}
    if len(arms) < 2 or any(a.get("scope", "variant") != "variant" or not a.get("publication_job_id") for a in arms) \
            or len({a["variant_id"] for a in arms}) != len(arms):
        return {**out, "status": "attribution_not_ready"}
    if any(int(a["leads"]) < min_leads_per_arm for a in arms):  # type: ignore[call-overload]
        return {**out, "status": "insufficient_data"}
    scored = []
    for a in arms:
        n, k = int(a["leads"]), int(a[metric])  # type: ignore[call-overload]
        if not 0 <= k <= n:
            raise ValueError("creative optimization successes must be between zero and leads")
        lo, hi = wilson_interval(k, n)
        scored.append((k / n, max(0.0, lo), min(1.0, hi), str(a["variant_id"]), a))
    scored.sort(key=lambda r: (-r[0], r[3]))
    winner = scored[0]
    if winner[1] <= max(r[2] for r in scored[1:]):
        return {**out, "status": "no_clear_winner"}
    alloc = {str(a["variant_id"]): int(a["allocation_bps"]) for a in arms}  # type: ignore[call-overload]
    if sum(alloc.values()) != 10_000:
        raise ValueError("creative allocation must sum to 10000 bps")
    losers = sorted(scored[1:], key=lambda r: (r[0], r[3]))
    shift = min(max_shift_bps, sum(max(0, alloc[r[3]] - exploration_floor_bps) for r in losers))
    if shift <= 0:
        return {**out, "status": "exploration_floor_reached", "winner_variant_id": winner[3]}
    left = shift
    for r in losers:
        take = min(max(0, alloc[r[3]] - exploration_floor_bps), left)
        alloc[r[3]] -= take
        left -= take
    alloc[winner[3]] += shift - left
    by = {r[3]: r for r in scored}
    ev = [{"variant_id": v, "publication_job_id": by[v][4]["publication_job_id"], "leads": int(by[v][4]["leads"]),  # type: ignore[call-overload]
           "rate": by[v][0], "confidence_low": by[v][1], "confidence_high": by[v][2],
           "current_allocation_bps": int(by[v][4]["allocation_bps"]), "proposed_allocation_bps": alloc[v]}  # type: ignore[call-overload]
          for v in (str(a["variant_id"]) for a in arms)]
    assert sum(e["proposed_allocation_bps"] for e in ev) == 10_000  # type: ignore[misc]
    return {**out, "status": "ready", "winner_variant_id": winner[3], "evidence": ev,
            "allocations": [(e["publication_job_id"], e["proposed_allocation_bps"]) for e in ev]}
