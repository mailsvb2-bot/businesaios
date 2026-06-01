from application.decision.decision_contract import (
    NON_SOVEREIGN_ENGINE_ROLE,
    build_executable_action_payload,
    canonical_request,
    start_trace,
)
from core.constraints.decision import DecisionConstraints
from core.decision.decision_contract import canonical_request as compat_canonical_request
from kernel.decision_candidate import DecisionCandidate
from kernel.decision_request import DecisionRequest


def test_canonical_request_defaults_are_honest_and_non_sovereign() -> None:
    request = canonical_request(constraints=DecisionConstraints(), request=None)

    assert request.business_id == "unknown_business"
    assert request.objective == DecisionConstraints().objective_name
    assert request.metadata["defaulted"] is True
    assert request.metadata["engine_role"] == NON_SOVEREIGN_ENGINE_ROLE


def test_canonical_request_rejects_blank_fields() -> None:
    try:
        canonical_request(
            constraints=DecisionConstraints(),
            request=DecisionRequest(business_id=" ", objective=DecisionConstraints().objective_name, input_bundle_id="bundle_1"),
        )
    except ValueError as exc:
        assert "business_id" in str(exc)
    else:
        raise AssertionError("blank business_id must fail closed")


def test_trace_and_action_share_single_contract_surface() -> None:
    constraints = DecisionConstraints()
    request = DecisionRequest(business_id="biz_1", objective=constraints.objective_name, input_bundle_id="bundle_1")
    trace = start_trace(request=request, candidate_count=3)
    candidate = DecisionCandidate(
        action_type="launch_campaign",
        channel="ads",
        score=1.0,
        expected_value=10.0,
        confidence=0.9,
        payload={"budget": 100},
    )

    payload = build_executable_action_payload(candidate=candidate, trace=trace, request=request, constraints=constraints)

    assert trace.metadata["decision_engine_role"] == NON_SOVEREIGN_ENGINE_ROLE
    assert trace.metadata["decision_surface"] == "core.application.decision_service.DecisionService"
    assert payload["decision_id"] == trace.decision_id
    assert payload["correlation_id"] == request.request_id
    assert payload["payload"]["candidate_id"] == candidate.candidate_id


def test_legacy_decision_contract_path_is_thin_wrapper() -> None:
    assert compat_canonical_request is canonical_request
