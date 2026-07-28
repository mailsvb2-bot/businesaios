from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

from application.business_autonomy.adapters.telegram_production_adapter import TelegramProductionAdapter
from application.business_autonomy.channel_contracts import ChannelExecutionEnvelope, ChannelIdentity, ChannelKind
from application.business_autonomy.contracts import (
    BusinessExecutionRequest,
    BusinessGoalEnvelope,
    ExecutionVerdict,
    IntegrationMode,
    PolicyConstraint,
)
from application.business_autonomy.guards import (
    ApprovalStatus,
    BusinessApprovalGate,
    BusinessBlastRadiusGuard,
    BusinessBudgetGuard,
    BusinessIdempotencyReservationStatus,
    BusinessIdempotencyStore,
    BusinessOperatorOverridePolicy,
    OperatorOverrideMode,
)
from application.business_autonomy.persistence import PersistentBusinessApprovalGate
from governance.approval_store import InMemoryApprovalStore
from runtime.business_autonomy.bootstrap import build_business_autonomy_guarded_service


def _request(
    *,
    goal_type: str = "internal_read",
    payload: dict | None = None,
    metadata: dict | None = None,
    constraints: tuple[PolicyConstraint, ...] = (),
    simulation: bool = False,
) -> BusinessExecutionRequest:
    return BusinessExecutionRequest(
        envelope=BusinessGoalEnvelope(
            business_id="biz-a",
            goal_id="goal-a",
            goal_type=goal_type,
            goal_payload=dict(payload or {}),
            simulation=simulation,
            constraints=constraints,
            metadata={"tenant_id": "tenant-a", **dict(metadata or {})},
        ),
        integration_mode=IntegrationMode.POLICY_GUARDED_DELEGATED,
        correlation_id="exec-a",
        idempotency_key="idem-a",
    )


def test_request_metadata_cannot_self_approve_or_force_allow() -> None:
    request = _request(metadata={"approved_by": "attacker", "operator_override_mode": "force_allow"})
    approval = BusinessApprovalGate().evaluate(request=request, requires_approval=True)
    override = BusinessOperatorOverridePolicy().evaluate(request)

    assert approval.status is ApprovalStatus.PENDING
    assert override.mode is OperatorOverrideMode.NONE


def test_persistent_approval_ignores_approved_by_metadata() -> None:
    gate = PersistentBusinessApprovalGate(store=InMemoryApprovalStore())
    request = _request(metadata={"approved_by": "attacker"})

    decision = gate.evaluate(request=request, requires_approval=True)

    assert decision.status is ApprovalStatus.PENDING


def test_paid_and_mass_write_actions_fail_closed_without_limits() -> None:
    paid = _request(goal_type="payment_capture", payload={"estimated_cost": 10.0})
    mass = _request(goal_type="message_send", payload={"outbound_count": 100})

    assert BusinessBudgetGuard().evaluate(paid).allowed is False
    assert BusinessBlastRadiusGuard().evaluate(mass).allowed is False


def test_invalid_cost_never_becomes_zero() -> None:
    request = _request(goal_type="payment_capture", payload={"estimated_cost": "not-a-number"})

    verdict = BusinessBudgetGuard().evaluate(request)

    assert verdict.allowed is False
    assert verdict.safety_verdict["reason"] == "invalid_estimated_cost"


def test_zero_cost_read_only_action_remains_available() -> None:
    request = _request(goal_type="analytics_read", payload={"estimated_cost": 0, "outbound_count": 1})

    assert BusinessBudgetGuard().evaluate(request).allowed is True
    assert BusinessBlastRadiusGuard().evaluate(request).allowed is True


def test_idempotency_reservation_is_atomic_before_effect() -> None:
    store = BusinessIdempotencyStore()

    def reserve(index: int):
        return store.reserve("tenant-a:biz-a:idem-a", owner_id=f"worker-{index}").status

    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(reserve, range(32)))

    assert statuses.count(BusinessIdempotencyReservationStatus.ACCEPTED) == 1
    assert statuses.count(BusinessIdempotencyReservationStatus.IN_PROGRESS) == 31


def test_static_production_adapter_never_claims_live_success() -> None:
    adapter = TelegramProductionAdapter()
    identity = ChannelIdentity(
        business_id="biz-a",
        tenant_id="tenant-a",
        channel_kind=ChannelKind.CHATBOT,
        adapter_key=adapter.adapter_key,
        external_ref="telegram://biz-a",
    )
    envelope = ChannelExecutionEnvelope(
        identity=identity,
        route_key="tenant-a:biz-a",
        operation="message_send",
        payload={"text": "hello"},
    )

    live = asyncio.run(adapter.execute(envelope=envelope, request=_request(goal_type="message_send")))
    simulated = asyncio.run(adapter.execute(envelope=envelope, request=_request(goal_type="message_send", simulation=True)))

    assert live.verdict is ExecutionVerdict.REJECTED
    assert live.metadata["external_effect"] is False
    assert simulated.verdict is ExecutionVerdict.SIMULATED
    assert simulated.metadata["external_effect"] is False


def test_missing_tenant_and_unknown_business_fail_closed(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    service = build_business_autonomy_guarded_service()
    missing_tenant = BusinessExecutionRequest(
        envelope=BusinessGoalEnvelope(
            business_id="unknown-business",
            goal_id="goal-a",
            goal_type="internal_read",
            goal_payload={},
            metadata={},
        ),
        integration_mode=IntegrationMode.POLICY_GUARDED_DELEGATED,
    )
    explicit_unknown = _request()

    missing_result = asyncio.run(service.execute(missing_tenant))
    unknown_result = asyncio.run(service.execute(explicit_unknown))

    assert missing_result.verdict is ExecutionVerdict.REJECTED
    assert "tenant_id is required" in missing_result.message
    assert unknown_result.verdict is ExecutionVerdict.REJECTED
    assert "not explicitly onboarded" in unknown_result.message
