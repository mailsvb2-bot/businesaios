from __future__ import annotations

from acquisition.cac_model import CacInputs, CustomerAcquisitionCostModel


def test_cac_model_evaluates_sustainable_unit_economics() -> None:
    snapshot = CustomerAcquisitionCostModel().evaluate(CacInputs(total_budget=1000.0, acquired_customers=20, gross_margin_ltv=300.0, max_cac_to_ltv_ratio=0.33, payback_horizon_months=12.0, expected_monthly_margin_per_customer=20.0, setup_cost=100.0))
    assert snapshot.setup_cost_share == 5.0
    assert snapshot.variable_cac == 45.0
    assert snapshot.blended_cac == 50.0
    assert snapshot.max_sustainable_cac == 99.0
    assert snapshot.ltv_to_cac_ratio == 6.0
    assert snapshot.payback_months == 2.5
    assert snapshot.sustainable is True
    assert snapshot.reasons == ()


def test_cac_model_flags_unsustainable_cac() -> None:
    snapshot = CustomerAcquisitionCostModel().evaluate(CacInputs(total_budget=2000.0, acquired_customers=10, gross_margin_ltv=300.0, max_cac_to_ltv_ratio=0.33, payback_horizon_months=6.0, expected_monthly_margin_per_customer=10.0))
    assert snapshot.blended_cac == 200.0
    assert snapshot.max_sustainable_cac == 99.0
    assert snapshot.sustainable is False
    assert "cac_above_sustainable_threshold" in snapshot.reasons
    assert "payback_too_slow" in snapshot.reasons


def test_cac_model_flags_missing_customers_and_ltv_cases() -> None:
    model = CustomerAcquisitionCostModel()
    missing_customers = model.evaluate(CacInputs(total_budget=500.0, acquired_customers=0, gross_margin_ltv=200.0))
    missing_both = model.evaluate(CacInputs(total_budget=500.0, acquired_customers=0, gross_margin_ltv=0.0))
    missing_ltv = model.evaluate(CacInputs(total_budget=500.0, acquired_customers=10, gross_margin_ltv=0.0, expected_monthly_margin_per_customer=50.0))
    assert missing_customers.reasons == ("no_acquired_customers",)
    assert missing_both.reasons == ("no_acquired_customers", "no_gross_margin_ltv")
    assert "no_gross_margin_ltv" in missing_ltv.reasons
