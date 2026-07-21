from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, tzinfo
from math import inf, nan

import pytest

from billing.plan_contract import (
    BillingPlanBinding,
    BillingPlanSpec,
    PlanQuotaLimit,
    PlanRateCardItem,
)
from tenancy.tenant_contract import TenantPlan

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _NoOffset(tzinfo):
    def utcoffset(self, dt):
        return None

    def dst(self, dt):
        return None


def _quota(**changes) -> PlanQuotaLimit:
    values = {
        "dimension": " actions ",
        "limit": 10,
        "window": " DAY ",
        "hard_stop": True,
        "metadata": {"nested": {"value": 1}},
    }
    values.update(changes)
    return PlanQuotaLimit(**values)


def _rate(**changes) -> PlanRateCardItem:
    values = {
        "meter_key": " actions ",
        "unit_price": 0.25,
        "currency": " usd ",
        "unit_name": " request ",
        "included_units": 2,
        "metadata": {"nested": {"value": 1}},
    }
    values.update(changes)
    return PlanRateCardItem(**values)


def _plan(**changes) -> BillingPlanSpec:
    values = {
        "plan_id": TenantPlan.GROWTH,
        "display_name": " Growth ",
        "version": " v2 ",
        "quota_limits": (_quota(),),
        "rate_card": (_rate(),),
        "features": {" exports ": True, "audit": False},
        "metadata": {"nested": {"value": 1}},
        "created_at": NOW,
    }
    values.update(changes)
    return BillingPlanSpec(**values)


def test_quota_normalizes_deeply_and_rejects_coercion() -> None:
    source = _quota()
    normalized = source.normalized_copy()
    assert normalized.dimension == "actions"
    assert normalized.window == "day"
    assert normalized.limit == 10.0
    normalized.metadata["nested"]["value"] = 9
    assert source.metadata["nested"]["value"] == 1

    invalid = [
        _quota(dimension=1),
        _quota(dimension=" "),
        _quota(window=1),
        _quota(window=" "),
        _quota(limit=True),
        _quota(limit="10"),
        _quota(limit=-1),
        _quota(limit=nan),
        _quota(limit=inf),
        _quota(hard_stop=1),
        _quota(metadata=[]),
    ]
    for item in invalid:
        with pytest.raises(ValueError):
            item.validate()


def test_rate_card_calculates_and_rejects_non_finite_or_coercible_values() -> None:
    source = _rate()
    normalized = source.normalized_copy()
    assert normalized.meter_key == "actions"
    assert normalized.currency == "USD"
    assert normalized.unit_name == "request"
    assert normalized.billable_units(1) == 0.0
    assert normalized.billable_units(6) == 4.0
    assert normalized.charge_for(6) == 1.0
    normalized.metadata["nested"]["value"] = 9
    assert source.metadata["nested"]["value"] == 1

    invalid = [
        _rate(meter_key=1),
        _rate(meter_key=" "),
        _rate(currency=1),
        _rate(currency=" "),
        _rate(unit_name=1),
        _rate(unit_name=" "),
        _rate(unit_price=True),
        _rate(unit_price="1"),
        _rate(unit_price=-1),
        _rate(unit_price=nan),
        _rate(included_units=True),
        _rate(included_units="2"),
        _rate(included_units=-1),
        _rate(included_units=inf),
        _rate(metadata=[]),
    ]
    for item in invalid:
        with pytest.raises(ValueError):
            item.validate()
    for quantity in (True, "2", -1, nan, inf):
        with pytest.raises(ValueError):
            normalized.billable_units(quantity)


def test_plan_normalizes_deeply_and_queries_contract_state() -> None:
    source = _plan()
    normalized = source.normalized_copy()
    assert normalized.display_name == "Growth"
    assert normalized.version == "v2"
    assert normalized.features == {"exports": True, "audit": False}
    assert normalized.quota_for("actions").limit == 10.0
    assert normalized.quota_for("actions", window=" DAY ").window == "day"
    assert normalized.quota_for("missing") is None
    assert normalized.quota_for("actions", window="month") is None
    assert normalized.rate_for("actions").currency == "USD"
    assert normalized.rate_for("missing") is None
    assert normalized.feature_enabled("exports") is True
    assert normalized.feature_enabled("missing") is False
    assert normalized.feature_enabled("missing", default=True) is True
    normalized.metadata["nested"]["value"] = 9
    normalized.quota_limits[0].metadata["nested"]["value"] = 8
    normalized.rate_card[0].metadata["nested"]["value"] = 7
    assert source.metadata["nested"]["value"] == 1
    assert source.quota_limits[0].metadata["nested"]["value"] == 1
    assert source.rate_card[0].metadata["nested"]["value"] == 1


def test_plan_rejects_malformed_structure_duplicates_and_feature_flags() -> None:
    invalid = [
        _plan(plan_id="growth"),
        _plan(display_name=1),
        _plan(display_name=" "),
        _plan(version=1),
        _plan(version=" "),
        _plan(created_at=datetime(2026, 1, 1)),
        _plan(created_at=datetime(2026, 1, 1, tzinfo=_NoOffset())),
        _plan(quota_limits=[]),
        _plan(rate_card=[]),
        _plan(features=[]),
        _plan(metadata=[]),
        _plan(quota_limits=(object(),)),
        _plan(rate_card=(object(),)),
        _plan(quota_limits=(_quota(), _quota(dimension="actions", window="day"))),
        _plan(rate_card=(_rate(), _rate(meter_key="actions"))),
        _plan(features={1: True}),
        _plan(features={" ": True}),
        _plan(features={"a": 1}),
        _plan(features={"a": True, " a ": False}),
    ]
    for plan in invalid:
        with pytest.raises(ValueError):
            plan.validate()


def test_plan_query_inputs_fail_closed() -> None:
    plan = _plan().normalized_copy()
    for value in (1, " "):
        with pytest.raises(ValueError):
            plan.quota_for(value)
        with pytest.raises(ValueError):
            plan.rate_for(value)
        with pytest.raises(ValueError):
            plan.feature_enabled(value)
    with pytest.raises(ValueError):
        plan.quota_for("actions", window=1)
    with pytest.raises(ValueError):
        plan.quota_for("actions", window=" ")
    with pytest.raises(ValueError, match="default must be a boolean"):
        plan.feature_enabled("missing", default=1)
    forged = replace(plan, features={"exports": 1})
    with pytest.raises(ValueError, match="feature flags must be booleans"):
        forged.feature_enabled("exports")


def test_binding_is_tenant_strict_aware_and_deeply_snapshotted() -> None:
    source = BillingPlanBinding(
        tenant_id=" tenant-a ",
        plan_id=TenantPlan.GROWTH,
        bound_at=NOW,
        effective_from=NOW,
        overrides={"nested": {"value": 1}},
    )
    normalized = source.normalized_copy()
    assert normalized.tenant_id == "tenant-a"
    normalized.overrides["nested"]["value"] = 9
    assert source.overrides["nested"]["value"] == 1

    invalid = [
        replace(source, tenant_id=1),
        replace(source, tenant_id=" "),
        replace(source, plan_id="growth"),
        replace(source, bound_at=datetime(2026, 1, 1)),
        replace(source, bound_at=datetime(2026, 1, 1, tzinfo=_NoOffset())),
        replace(source, effective_from=datetime(2026, 1, 1)),
        replace(source, effective_from=datetime(2026, 1, 1, tzinfo=_NoOffset())),
        replace(source, overrides=[]),
    ]
    for binding in invalid:
        with pytest.raises(ValueError):
            binding.validate()
