from __future__ import annotations

from datetime import UTC, datetime, timedelta, tzinfo

import pytest

from billing.commercial_cycle_contract import (
    BillingCycleWindow,
    CommercialCollectionAttempt,
    CommercialCollectionResult,
    DunningAction,
    ReconciliationDrift,
    SpendGuardVerdict,
    SubscriptionCommercialEnvelope,
    SubscriptionLifecycleStatus,
    _add_calendar_months,
    _replace_year_safe,
    _require_bool,
    _require_mapping,
    next_cycle_window,
    require_aware_datetime,
    require_commercial_int,
    utc_now,
)

START = datetime(2024, 1, 31, 12, tzinfo=UTC)


class _NaiveTz(tzinfo):
    def utcoffset(self, dt):
        return None

    def dst(self, dt):
        return None

    def tzname(self, dt):
        return "none"


def _cycle() -> BillingCycleWindow:
    return BillingCycleWindow(
        start_at=START,
        end_at=datetime(2024, 2, 29, 12, tzinfo=UTC),
        anchor="monthly",
    )


def test_datetime_and_scalar_helpers_fail_closed() -> None:
    assert utc_now().utcoffset() == timedelta(0)
    assert require_aware_datetime("at", START) is START
    for value in ("2024-01-01", datetime(2024, 1, 1), datetime(2024, 1, 1, tzinfo=_NaiveTz())):
        with pytest.raises(ValueError, match="at must"):
            require_aware_datetime("at", value)  # type: ignore[arg-type]

    assert require_commercial_int("money", 0, minimum=0) == 0
    assert require_commercial_int("attempt", 1, minimum=1) == 1
    assert require_commercial_int("signed", -2) == -2
    for value in (True, 1.2, "1", None):
        with pytest.raises(ValueError, match="must be an integer"):
            require_commercial_int("money", value)
    with pytest.raises(ValueError, match="must be >= 0"):
        require_commercial_int("money", -1, minimum=0)
    with pytest.raises(ValueError, match="must be > 0"):
        require_commercial_int("attempt", 0, minimum=1)

    assert _require_bool("flag", True) is True
    with pytest.raises(ValueError, match="must be a boolean"):
        _require_bool("flag", 1)
    mapping = {"a": 1}
    assert _require_mapping("meta", mapping) is mapping
    with pytest.raises(ValueError, match="must be a mapping"):
        _require_mapping("meta", [])


def test_calendar_helpers_preserve_end_of_month_and_validate_ranges() -> None:
    assert _add_calendar_months(START, 1) == datetime(2024, 2, 29, 12, tzinfo=UTC)
    assert _add_calendar_months(datetime(2023, 1, 31, tzinfo=UTC), 1) == datetime(2023, 2, 28, tzinfo=UTC)
    assert _replace_year_safe(datetime(2024, 2, 29, tzinfo=UTC), 2025) == datetime(2025, 2, 28, tzinfo=UTC)
    with pytest.raises(ValueError, match="months must be an integer"):
        _add_calendar_months(START, True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="out of range"):
        _add_calendar_months(datetime(9999, 12, 1, tzinfo=UTC), 1)
    with pytest.raises(ValueError, match="year must be > 0"):
        _replace_year_safe(START, 0)


def test_cycle_window_requires_canonical_interval_and_real_awareness() -> None:
    cycle = _cycle()
    cycle.validate()
    assert cycle.duration_seconds == 29 * 24 * 60 * 60
    assert cycle.contains(START)
    assert not cycle.contains(cycle.end_at)

    invalid = (
        BillingCycleWindow(datetime(2024, 1, 1), datetime(2024, 2, 1, tzinfo=UTC)),
        BillingCycleWindow(START, START),
        BillingCycleWindow(START, START + timedelta(days=1), anchor="MONTHLY"),
        BillingCycleWindow(START, START + timedelta(days=1), anchor="quarterly"),
    )
    for window in invalid:
        with pytest.raises(ValueError):
            window.validate()
    with pytest.raises(ValueError, match="when must"):
        cycle.contains(datetime(2024, 2, 1))


def test_next_cycle_window_supports_only_declared_intervals() -> None:
    weekly = next_cycle_window(current_start_at=START, interval="weekly")
    monthly = next_cycle_window(current_start_at=START, interval="monthly")
    yearly = next_cycle_window(
        current_start_at=datetime(2024, 2, 29, tzinfo=UTC),
        interval="yearly",
    )
    defaulted = next_cycle_window(current_start_at=START, interval="")
    assert weekly.end_at == START + timedelta(days=7)
    assert monthly.end_at == datetime(2024, 2, 29, 12, tzinfo=UTC)
    assert yearly.end_at == datetime(2025, 2, 28, tzinfo=UTC)
    assert defaulted.anchor == "monthly"
    with pytest.raises(ValueError, match="interval must"):
        next_cycle_window(current_start_at=START, interval="annual")
    with pytest.raises(ValueError, match="current_start_at"):
        next_cycle_window(current_start_at=datetime(2024, 1, 1), interval="monthly")


def test_subscription_envelope_validates_enum_cycle_and_status_dates() -> None:
    active = SubscriptionCommercialEnvelope(
        tenant_id="tenant-a",
        subscription_id="sub-1",
        plan_id="plan-1",
        status=SubscriptionLifecycleStatus.ACTIVE,
        cycle=_cycle(),
    )
    active.validate()
    trial = SubscriptionCommercialEnvelope(
        tenant_id="tenant-a",
        subscription_id="sub-1",
        plan_id="plan-1",
        status=SubscriptionLifecycleStatus.TRIALING,
        cycle=_cycle(),
        trial_ends_at=START + timedelta(days=3),
    )
    trial.validate()
    grace = SubscriptionCommercialEnvelope(
        tenant_id="tenant-a",
        subscription_id="sub-1",
        plan_id="plan-1",
        status=SubscriptionLifecycleStatus.GRACE,
        cycle=_cycle(),
        grace_until=START + timedelta(days=3),
    )
    grace.validate()
    canceled = SubscriptionCommercialEnvelope(
        tenant_id="tenant-a",
        subscription_id="sub-1",
        plan_id="plan-1",
        status=SubscriptionLifecycleStatus.CANCELED,
        cycle=_cycle(),
        canceled_at=START + timedelta(days=1),
    )
    canceled.validate()

    cases = (
        ({"tenant_id": ""}, "tenant"),
        ({"subscription_id": ""}, "subscription_id"),
        ({"plan_id": ""}, "plan_id"),
        ({"status": "active"}, "status"),
        ({"cycle": object()}, "cycle"),
        ({"metadata": []}, "metadata"),
        ({"trial_ends_at": datetime(2024, 2, 1)}, "trial_ends_at"),
        ({"trial_ends_at": START - timedelta(seconds=1)}, "trial_ends_at"),
        ({"grace_until": START - timedelta(seconds=1)}, "grace_until"),
        ({"canceled_at": START - timedelta(seconds=1)}, "canceled_at"),
        ({"status": SubscriptionLifecycleStatus.TRIALING}, "trial_ends_at"),
        ({"status": SubscriptionLifecycleStatus.GRACE}, "grace_until"),
        ({"status": SubscriptionLifecycleStatus.CANCELED}, "canceled_at"),
        ({"canceled_at": START + timedelta(days=1)}, "only allowed"),
    )
    base = dict(active.__dict__)
    for changes, message in cases:
        values = {**base, **changes}
        with pytest.raises((ValueError, TypeError), match=message):
            SubscriptionCommercialEnvelope(**values).validate()


def test_collection_attempt_rejects_coercible_money_and_attempt_numbers() -> None:
    attempt = CommercialCollectionAttempt(
        invoice_id="inv-1",
        tenant_id="tenant-a",
        amount_minor=100,
        currency="USD",
        provider_name="stripe",
        idempotency_key="key-1",
        attempt_no=1,
        scheduled_at=START,
    )
    attempt.validate()
    cases = (
        ({"tenant_id": ""}, "tenant"),
        ({"invoice_id": ""}, "invoice_id"),
        ({"amount_minor": True}, "integer"),
        ({"amount_minor": 1.5}, "integer"),
        ({"amount_minor": -1}, ">= 0"),
        ({"currency": ""}, "currency"),
        ({"provider_name": ""}, "provider_name"),
        ({"idempotency_key": ""}, "idempotency_key"),
        ({"attempt_no": "1"}, "integer"),
        ({"attempt_no": 0}, "> 0"),
        ({"scheduled_at": datetime(2024, 1, 1)}, "scheduled_at"),
        ({"metadata": []}, "metadata"),
    )
    base = dict(attempt.__dict__)
    for changes, message in cases:
        with pytest.raises((ValueError, TypeError), match=message):
            CommercialCollectionAttempt(**{**base, **changes}).validate()


def test_collection_result_enforces_boolean_and_outcome_consistency() -> None:
    success = CommercialCollectionResult(
        invoice_id="inv-1",
        tenant_id="tenant-a",
        provider_name="stripe",
        successful=True,
        external_reference="pi-1",
        processed_at=START,
    )
    success.validate()
    CommercialCollectionResult(
        invoice_id="inv-1",
        tenant_id="tenant-a",
        provider_name="stripe",
        successful=True,
        processed_at=START,
        metadata={"noop": True},
    ).validate()
    failure = CommercialCollectionResult(
        invoice_id="inv-1",
        tenant_id="tenant-a",
        provider_name="stripe",
        successful=False,
        failure_reason="declined",
        processed_at=START,
    )
    failure.validate()
    CommercialCollectionResult(
        invoice_id="inv-1",
        tenant_id="tenant-a",
        provider_name="stripe",
        successful=False,
        external_reference="ref-on-failure",
        failure_reason="declined",
        processed_at=START,
        metadata={"provider_reference_on_failure": True},
    ).validate()

    cases = (
        ({"tenant_id": ""}, "tenant"),
        ({"invoice_id": ""}, "invoice_id"),
        ({"provider_name": ""}, "provider_name"),
        ({"successful": 1}, "boolean"),
        ({"retryable": 1}, "boolean"),
        ({"retryable": True}, "cannot be retryable"),
        ({"processed_at": datetime(2024, 1, 1)}, "processed_at"),
        ({"metadata": []}, "metadata"),
        ({"failure_reason": "error"}, "cannot include"),
        ({"external_reference": None}, "external_reference"),
    )
    base = dict(success.__dict__)
    for changes, message in cases:
        with pytest.raises((ValueError, TypeError), match=message):
            CommercialCollectionResult(**{**base, **changes}).validate()

    failure_base = dict(failure.__dict__)
    with pytest.raises(ValueError, match="failure_reason"):
        CommercialCollectionResult(**{**failure_base, "failure_reason": ""}).validate()
    with pytest.raises(ValueError, match="provider_reference_on_failure"):
        CommercialCollectionResult(**{**failure_base, "external_reference": "x"}).validate()


def test_dunning_action_requires_strict_attempt_and_mapping() -> None:
    action = DunningAction(
        invoice_id="inv-1",
        tenant_id="tenant-a",
        attempt_no=1,
        execute_at=START,
        channel="email",
        template_key="billing.dunning.1",
    )
    action.validate()
    cases = (
        ({"tenant_id": ""}, "tenant"),
        ({"invoice_id": ""}, "invoice_id"),
        ({"attempt_no": True}, "integer"),
        ({"attempt_no": 0}, "> 0"),
        ({"execute_at": datetime(2024, 1, 1)}, "execute_at"),
        ({"channel": ""}, "channel"),
        ({"template_key": ""}, "template_key"),
        ({"metadata": []}, "metadata"),
    )
    base = dict(action.__dict__)
    for changes, message in cases:
        with pytest.raises((ValueError, TypeError), match=message):
            DunningAction(**{**base, **changes}).validate()


def test_spend_guard_verdict_rejects_coercion() -> None:
    verdict = SpendGuardVerdict(
        tenant_id="tenant-a",
        allowed=True,
        projected_minor=100,
        limit_minor=200,
        remaining_minor=100,
        reason="ok",
    )
    verdict.validate()
    SpendGuardVerdict(
        tenant_id="tenant-a",
        allowed=False,
        projected_minor=0,
        limit_minor=None,
        remaining_minor=None,
        reason="mixed_currency",
    ).validate()
    cases = (
        ({"tenant_id": ""}, "tenant"),
        ({"allowed": 1}, "boolean"),
        ({"projected_minor": "100"}, "integer"),
        ({"projected_minor": -1}, ">= 0"),
        ({"limit_minor": True}, "integer"),
        ({"limit_minor": -1}, ">= 0"),
        ({"remaining_minor": 1.5}, "integer"),
        ({"remaining_minor": -1}, ">= 0"),
        ({"reason": ""}, "reason"),
        ({"metadata": []}, "metadata"),
    )
    base = dict(verdict.__dict__)
    for changes, message in cases:
        with pytest.raises((ValueError, TypeError), match=message):
            SpendGuardVerdict(**{**base, **changes}).validate()


def test_reconciliation_drift_requires_exact_delta_and_integer_money() -> None:
    drift = ReconciliationDrift(
        tenant_id="tenant-a",
        drift_key="invoice_vs_ledger",
        expected_minor=100,
        observed_minor=130,
        delta_minor=30,
        severity="medium",
    )
    drift.validate()
    cases = (
        ({"tenant_id": ""}, "tenant"),
        ({"drift_key": ""}, "drift_key"),
        ({"expected_minor": True}, "integer"),
        ({"observed_minor": 130.5}, "integer"),
        ({"delta_minor": "30"}, "integer"),
        ({"delta_minor": 29}, "must equal"),
        ({"severity": ""}, "severity"),
        ({"details": []}, "details"),
    )
    base = dict(drift.__dict__)
    for changes, message in cases:
        with pytest.raises((ValueError, TypeError), match=message):
            ReconciliationDrift(**{**base, **changes}).validate()
