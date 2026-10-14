"""Donor Yandex analytics parity: source identity, money, and canonical outcomes."""
from datetime import date

import pytest

from application.analytics.yandex_direct_growth_projection import (
    CanonicalAdOutcomes, ProviderAdMetrics, TrackedAd,
    period_window, project_yandex_growth,
)

def ad(connection="c1", campaign="42", item="11", currency="RUB"):
    return TrackedAd(connection, campaign, item, currency, "Test campaign")

def metric(connection="c1", campaign="42", item="11", cost=8_000_000):
    return ProviderAdMetrics(connection, campaign, item, 100, 10, cost)

def outcomes(campaign="42", lead_ids=("lead1", "lead2"), won_ids=("won1",)):
    return CanonicalAdOutcomes(campaign, frozenset(lead_ids), frozenset({"booking1"}), frozenset(won_ids))

def project(ads=None, rows=None, facts=None):
    return project_yandex_growth(
        ads=[ad()] if ads is None else ads,
        provider_rows=[metric()] if rows is None else rows,
        canonical_outcomes=[outcomes()] if facts is None else facts,
        date_from="2026-10-01", date_to="2026-10-14",
    )

def test_complete_scoped_campaign_and_verified_outcomes():
    result = project()
    assert result.currency == "RUB"
    assert result.cost_micros == 8_000_000
    assert (result.leads, result.bookings, result.won) == (2, 1, 1)
    assert result.campaigns[0].cpl_micros == 4_000_000
    assert result.campaigns[0].cac_micros == 8_000_000
    assert result.campaigns[0].ctr_percent == 10

def test_mixed_currencies_never_sum_money():
    result = project(
        ads=[ad(), ad("c2", "43", "12", "KZT")],
        rows=[metric(), metric("c2", "43", "12", 3_000_000)],
        facts=[outcomes(), outcomes("43", ("lead1", "lead3"), ("won2",))],
    )
    assert result.currency is None and result.cost_micros is None
    assert result.leads == 3 and result.won == 2
    assert {x.currency: x.cost_micros for x in result.campaigns} == {"RUB": 8_000_000, "KZT": 3_000_000}

@pytest.mark.parametrize("rows", [[], [metric(), metric()], [metric(campaign="43")], [metric(item="12")]])
def test_missing_duplicate_or_foreign_provider_evidence_fails_closed(rows):
    with pytest.raises(ValueError):
        project(rows=rows)

def test_foreign_attribution_rejected():
    with pytest.raises(ValueError, match="foreign_outcome_campaign"):
        project(facts=[outcomes("43")])

def test_invalid_spend_and_impressions_rejected():
    for cost in (-1, True, 1.5):
        with pytest.raises(ValueError):
            metric(cost=cost)
    with pytest.raises(ValueError):
        ProviderAdMetrics("c1", "42", "11", 1, 2, 1)

def test_period_and_empty_coverage():
    assert period_window(7, today=date(2026, 10, 14)) == ("2026-10-08", "2026-10-14")
    with pytest.raises(ValueError):
        period_window(31, today=date(2026, 10, 14))
    empty = project(ads=[], rows=[], facts=[])
    assert empty.campaigns == () and empty.cost_micros == 0 and empty.leads == 0
