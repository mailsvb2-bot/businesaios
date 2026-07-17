from application.decision import decision_contract as recommendation_contract
from application.decision.decision_contract import (
    NON_SOVEREIGN_ENGINE_ROLE,
    NON_SOVEREIGN_ENGINE_SURFACE,
    canonical_request,
    start_trace,
)
from core.constraints.decision import DecisionConstraints
from core.decision import decision_contract as compat_contract
from core.decision.decision_contract import canonical_request as compat_canonical_request
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
            request=DecisionRequest(
                business_id=" ",
                objective=DecisionConstraints().objective_name,
                input_bundle_id="bundle_1",
            ),
        )
    except ValueError as exc:
        assert "business_id" in str(exc)
    else:
        raise AssertionError("blank business_id must fail closed")


def test_trace_is_recommendation_only_and_builds_no_executable_action() -> None:
    constraints = DecisionConstraints()
    request = DecisionRequest(
        business_id="biz_1",
        objective=constraints.objective_name,
        input_bundle_id="bundle_1",
    )

    trace = start_trace(request=request, candidate_count=3)

    assert trace.request_id == request.request_id
    assert trace.metadata["decision_engine_role"] == NON_SOVEREIGN_ENGINE_ROLE
    assert trace.metadata["decision_surface"] == NON_SOVEREIGN_ENGINE_SURFACE
    assert trace.metadata["candidate_count"] == 3
    assert trace.metadata["executable"] is False
    assert "build_executable_action_payload" not in recommendation_contract.__dict__


def test_legacy_decision_contract_path_is_thin_wrapper() -> None:
    assert compat_canonical_request is canonical_request
    assert compat_contract.CANONICAL_OWNER_MODULE == (
        "application.decision.decision_contract"
    )
    assert "build_executable_action_payload" not in compat_contract.__dict__
    assert "build_executable_action_payload" not in compat_contract.__all__
