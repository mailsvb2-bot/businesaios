"""Read-only Yandex Direct outcome projection, adapted from ClientPlatform.

No credentials, provider writes, attribution ledger, or second event store.
Caller must supply verified provider observations and canonical outcome IDs.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable


@dataclass(frozen=True, slots=True)
class TrackedAd:
    connection_id: str
    campaign_id: str
    ad_id: str
    currency: str
    name: str = ""

    def __post_init__(self) -> None:
        for field in ("connection_id", "campaign_id", "ad_id", "currency"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"invalid_{field}")
        if not self.ad_id.isdecimal() or not self.campaign_id.isdecimal():
            raise ValueError("invalid_provider_identity")
        if not self.currency.isalpha() or len(self.currency) != 3:
            raise ValueError("invalid_currency")


@dataclass(frozen=True, slots=True)
class ProviderAdMetrics:
    connection_id: str
    campaign_id: str
    ad_id: str
    impressions: int
    clicks: int
    cost_micros: int

    def __post_init__(self) -> None:
        if any(type(v) is not int or v < 0 for v in (
            self.impressions, self.clicks, self.cost_micros
        )):
            raise ValueError("invalid_provider_metrics")
        if self.clicks > self.impressions:
            raise ValueError("clicks_exceed_impressions")


@dataclass(frozen=True, slots=True)
class CanonicalAdOutcomes:
    """Distinct canonical IDs; never raw customer text."""
    campaign_id: str
    lead_ids: frozenset[str]
    booking_ids: frozenset[str]
    won_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class CampaignGrowth:
    connection_id: str
    campaign_id: str
    currency: str
    name: str
    tracked_ads: int
    impressions: int
    clicks: int
    cost_micros: int | None
    leads: int
    bookings: int
    won: int

    @property
    def ctr_percent(self) -> float:
        return round(100 * self.clicks / self.impressions, 1) if self.impressions else 0.0

    @property
    def cpl_micros(self) -> int | None:
        return self.cost_micros // self.leads if self.cost_micros is not None and self.leads else None

    @property
    def cac_micros(self) -> int | None:
        return self.cost_micros // self.won if self.cost_micros is not None and self.won else None


@dataclass(frozen=True, slots=True)
class GrowthSnapshot:
    date_from: str
    date_to: str
    currency: str | None
    campaigns: tuple[CampaignGrowth, ...]
    impressions: int
    clicks: int
    cost_micros: int | None
    leads: int
    bookings: int
    won: int


def period_window(days: int, *, today: date) -> tuple[str, str]:
    if type(days) is not int or days not in (7, 30):
        raise ValueError("invalid_report_period")
    if not isinstance(today, date):
        raise ValueError("invalid_report_date")
    return (today - timedelta(days=days - 1)).isoformat(), today.isoformat()


def project_yandex_growth(
    *,
    ads: Iterable[TrackedAd],
    provider_rows: Iterable[ProviderAdMetrics],
    canonical_outcomes: Iterable[CanonicalAdOutcomes],
    date_from: str,
    date_to: str,
) -> GrowthSnapshot:
    """Fail closed on missing/foreign provider observations; dedupe canonical outcomes.

    Ads MUST be selected by the canonical tenant-scoped connection owner.
    Provider rows MUST be fetched through the canonical credentials/effects path.
    An absent row is not silently interpreted as zero advertising spend.
    """
    start, finish = date.fromisoformat(date_from), date.fromisoformat(date_to)
    if start > finish or (finish - start).days >= 31:
        raise ValueError("invalid_report_window")
    ad_by_key: dict[tuple[str, str], TrackedAd] = {}
    for ad in ads:
        key = (ad.connection_id, ad.ad_id)
        if key in ad_by_key and ad_by_key[key] != ad:
            raise ValueError("conflicting_tracked_ad")
        ad_by_key[key] = ad
    metrics: dict[tuple[str, str], ProviderAdMetrics] = {}
    for row in provider_rows:
        key = (row.connection_id, row.ad_id)
        ad = ad_by_key.get(key)
        if ad is None or ad.campaign_id != row.campaign_id:
            raise ValueError("untracked_provider_observation")
        if key in metrics:
            raise ValueError("duplicate_provider_observation")
        metrics[key] = row
    if set(metrics) != set(ad_by_key):
        raise ValueError("incomplete_provider_observations")
    outcomes: dict[str, tuple[set[str], set[str], set[str]]] = {}
    for row in canonical_outcomes:
        if not row.campaign_id or row.campaign_id in outcomes:
            raise ValueError("duplicate_or_invalid_outcome_campaign")
        values = (row.lead_ids, row.booking_ids, row.won_ids)
        if any(not isinstance(s, frozenset) or any(not isinstance(x, str) or not x for x in s) for s in values):
            raise ValueError("invalid_outcome_ids")
        outcomes[row.campaign_id] = tuple(map(set, values))
    unknown = set(outcomes) - {ad.campaign_id for ad in ad_by_key.values()}
    if unknown:
        raise ValueError("foreign_outcome_campaign")
    grouped: dict[tuple[str, str], list[TrackedAd]] = {}
    for ad in ad_by_key.values():
        grouped.setdefault((ad.connection_id, ad.campaign_id), []).append(ad)
    campaigns: list[CampaignGrowth] = []
    all_outcomes = [set(), set(), set()]
    for (connection, campaign), members in sorted(grouped.items()):
        currencies = {x.currency.upper() for x in members}
        if len(currencies) != 1:
            raise ValueError("mixed_currency_in_campaign")
        observed = [metrics[(x.connection_id, x.ad_id)] for x in members]
        counts = outcomes.get(campaign, (set(), set(), set()))
        for index in range(3):
            all_outcomes[index].update(counts[index])
        campaigns.append(CampaignGrowth(
            connection, campaign, next(iter(currencies)), members[0].name,
            len(members), sum(x.impressions for x in observed),
            sum(x.clicks for x in observed), sum(x.cost_micros for x in observed),
            *(len(x) for x in counts),
        ))
    currencies = {x.currency for x in campaigns}
    single_currency = next(iter(currencies)) if len(currencies) == 1 else None
    return GrowthSnapshot(
        date_from, date_to, single_currency, tuple(campaigns),
        sum(x.impressions for x in campaigns), sum(x.clicks for x in campaigns),
        sum(x.cost_micros for x in campaigns) if single_currency else (0 if not campaigns else None),
        *(len(x) for x in all_outcomes),
    )
