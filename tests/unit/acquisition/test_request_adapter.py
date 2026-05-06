from __future__ import annotations

from acquisition.feasibility_solver import AcquisitionFeasibilityRequest
from acquisition.request_adapter import AcquisitionPayloadError, request_from_payload


def test_request_adapter_builds_request() -> None:
    request = request_from_payload(
        {
            "target_customers": 5,
            "total_budget": 500.0,
            "daily_budget": 50.0,
            "cost_per_entry": 5.0,
            "gross_margin_ltv": 100.0,
            "stages": [{"name": "lead", "conversion_rate": 0.5}],
        }
    )
    assert isinstance(request, AcquisitionFeasibilityRequest)
    assert request.target_customers == 5
    assert request.stages[0].name == "lead"


def test_request_adapter_rejects_invalid_stage_shape() -> None:
    try:
        request_from_payload(
            {
                "target_customers": 5,
                "total_budget": 500.0,
                "daily_budget": 50.0,
                "cost_per_entry": 5.0,
                "gross_margin_ltv": 100.0,
                "stages": [1],
            }
        )
    except TypeError:
        pass
    else:
        raise AssertionError("TypeError was not raised for invalid stage")


def test_request_adapter_rejects_missing_required_fields() -> None:
    try:
        request_from_payload({"target_customers": 5})
    except AcquisitionPayloadError as exc:
        assert "missing required payload fields" in str(exc)
    else:
        raise AssertionError("AcquisitionPayloadError was not raised for missing fields")


def test_request_adapter_rejects_non_iterable_stages() -> None:
    try:
        request_from_payload(
            {
                "target_customers": 1,
                "total_budget": 1,
                "daily_budget": 1,
                "cost_per_entry": 1,
                "gross_margin_ltv": 1,
                "stages": "bad",
            }
        )
    except AcquisitionPayloadError as exc:
        assert "stages must be an iterable" in str(exc)
    else:
        raise AssertionError("AcquisitionPayloadError was not raised for invalid stages container")


def test_request_adapter_rejects_empty_stage_list() -> None:
    try:
        request_from_payload(
            {
                "target_customers": 1,
                "total_budget": 1,
                "daily_budget": 1,
                "cost_per_entry": 1,
                "gross_margin_ltv": 1,
                "stages": [],
            }
        )
    except AcquisitionPayloadError as exc:
        assert "stages must contain at least one stage" in str(exc)
    else:
        raise AssertionError("AcquisitionPayloadError was not raised for empty stages")


def test_request_adapter_rejects_missing_stage_conversion_rate() -> None:
    try:
        request_from_payload(
            {
                "target_customers": 1,
                "total_budget": 1,
                "daily_budget": 1,
                "cost_per_entry": 1,
                "gross_margin_ltv": 1,
                "stages": [{"name": "lead"}],
            }
        )
    except AcquisitionPayloadError as exc:
        assert "missing required stage fields" in str(exc)
    else:
        raise AssertionError("AcquisitionPayloadError was not raised for missing stage fields")
