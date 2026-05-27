from __future__ import annotations

from dataclasses import replace

from acquisition.feasibility_solver import (
    AcquisitionFeasibilityRequest,
    AcquisitionFeasibilityResult,
    FeasibilitySolver,
)
from acquisition.funnel_model import FunnelStage
from acquisition.public_api import create_acquisition_public_api, evaluate_acquisition_plan


def _request() -> AcquisitionFeasibilityRequest:
    return AcquisitionFeasibilityRequest(target_customers=10, total_budget=2200.0, daily_budget=200.0, cost_per_entry=10.0, gross_margin_ltv=1000.0, stages=(FunnelStage(name="traffic_to_lead", conversion_rate=0.5, avg_stage_days=7.0), FunnelStage(name="lead_to_sale", conversion_rate=0.2, avg_stage_days=7.0)), target_days=20.0, setup_cost=100.0, expected_monthly_margin_per_customer=100.0)


def test_public_api_evaluate_returns_feasibility_result() -> None:
    api = create_acquisition_public_api()
    result = api.evaluate(_request())
    assert isinstance(result, AcquisitionFeasibilityResult)
    assert result.feasible is True
    assert result.required_budget == 1100.0
    assert result.recommended_daily_budget == 55.0
    assert result.estimated_days == 14.0


class StubSolver:
    def __init__(self, result: AcquisitionFeasibilityResult) -> None:
        self.result = result
        self.call_count = 0

    def solve(self, request: AcquisitionFeasibilityRequest) -> AcquisitionFeasibilityResult:
        self.call_count += 1
        return self.result


def test_public_api_uses_injected_solver_without_duplicating_logic() -> None:
    request = _request()
    baseline = FeasibilitySolver().solve(request)
    expected = replace(baseline, feasible=False, summary="from_stub", reasons=("stubbed",))
    stub = StubSolver(expected)
    api = create_acquisition_public_api(solver=stub)
    result = api.evaluate(request)
    assert result.summary == "from_stub"
    assert result.reasons == ("stubbed",)
    assert stub.call_count == 1


def test_functional_entrypoint_uses_injected_solver() -> None:
    request = _request()
    baseline = FeasibilitySolver().solve(request)
    stub = StubSolver(replace(baseline, summary="from_stub", reasons=("stubbed",)))
    result = evaluate_acquisition_plan(request, solver=stub)
    assert result.summary == "from_stub"
    assert result.reasons == ("stubbed",)
    assert stub.call_count == 1
