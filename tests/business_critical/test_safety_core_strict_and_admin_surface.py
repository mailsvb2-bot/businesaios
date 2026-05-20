from __future__ import annotations

from application.business_autonomy.contracts import BusinessExecutionRequest, BusinessGoalEnvelope, IntegrationMode, PolicyConstraint
from application.business_autonomy.guards import BusinessBlastRadiusGuard, BusinessBudgetGuard
from application.business_autonomy.safety_core import SafetyRuntimePolicy, build_safety_core_admin_surface, validate_budget
from interfaces.api.business_autonomy_route_handlers import build_business_autonomy_route_handlers


def _request(*, metadata: dict[str, object] | None = None) -> BusinessExecutionRequest:
    return BusinessExecutionRequest(
        envelope=BusinessGoalEnvelope(
            business_id="site-safety",
            goal_id="strict-mode",
            goal_type="paid_campaign_launch",
            goal_payload={"estimated_cost": 1.0, "outbound_count": 1},
            constraints=(
                PolicyConstraint(name="monthly_budget_limit", value=10.0),
                PolicyConstraint(name="outbound_message_limit", value=10),
            ),
            metadata={"tenant_id": "tenant-safety", **dict(metadata or {})},
        ),
        integration_mode=IntegrationMode.PLATFORM_DIRECT,
        correlation_id="strict-mode",
        idempotency_key="strict-mode",
    )


def test_strict_rust_required_fails_closed_when_unavailable() -> None:
    policy = SafetyRuntimePolicy.strict_rust_required(rust_available=False)
    verdict = validate_budget(estimated_minor=1, limit_minor=1, policy=policy)

    assert verdict.allowed is False
    assert verdict.reason == "rust_safety_core_unavailable"
    assert verdict.source == "rust_safety_core_required"


def test_owner_guards_fail_closed_when_strict_rust_required_but_unavailable() -> None:
    request = _request(metadata={"safety_core_mode": "strict_rust_required", "rust_safety_core_available": False})

    budget = BusinessBudgetGuard().evaluate(request)
    blast = BusinessBlastRadiusGuard().evaluate(request)

    assert budget.allowed is False
    assert budget.safety_verdict == {
        "allowed": False,
        "reason": "rust_safety_core_unavailable",
        "source": "rust_safety_core_required",
    }
    assert blast.allowed is False
    assert blast.safety_verdict == budget.safety_verdict


def test_owner_guards_allow_python_mirror_default_mode() -> None:
    request = _request()

    budget = BusinessBudgetGuard().evaluate(request)
    blast = BusinessBlastRadiusGuard().evaluate(request)

    assert budget.allowed is True
    assert budget.safety_verdict["reason"] == "allow"
    assert blast.allowed is True
    assert blast.safety_verdict["reason"] == "allow"


def test_safety_core_admin_surface_is_visible_and_fail_closed() -> None:
    surface = build_safety_core_admin_surface(rust_available=False, mode="strict_rust_required", parity_checked=True, drift_detected=False)

    assert surface["surface"] == "business_autonomy_safety_core"
    assert surface["admin_visibility"] is True
    assert surface["decision_core_replaced"] is False
    assert surface["ffi_enabled"] is False
    assert surface["runtime_policy"] == "fail_closed"
    assert surface["strict_rust_required_verdict"]["allowed"] is False
    assert surface["strict_rust_required_verdict"]["reason"] == "rust_safety_core_unavailable"
    assert surface["golden_fixture_version"] == "businessaios_safety_core_golden.v1"
    assert surface["rust_fixture_runner_required"] is True
    assert surface["msrv"] == "1.75.0"
    assert surface["rust_edition"] == "2021"
    assert surface["dependency_policy"] == "allowlist"
    assert surface["allowed_direct_dependencies"] == ["serde", "serde_json"]
    assert surface["parity_checked"] is True
    assert surface["drift_detected"] is False


def test_route_handlers_expose_safety_core_surface() -> None:
    handlers = build_business_autonomy_route_handlers(stack={})
    surface = handlers.get_safety_core_surface(rust_available=False, mode="strict_rust_required")

    assert surface["surface"] == "business_autonomy_safety_core"
    assert surface["admin_visibility"] is True
    assert surface["strict_rust_required_verdict"]["reason"] == "rust_safety_core_unavailable"
    assert surface["golden_fixture_version"] == "businessaios_safety_core_golden.v1"
    assert surface["msrv"] == "1.75.0"
    assert surface["dependency_policy"] == "allowlist"
    assert surface["drift_detected"] is False
