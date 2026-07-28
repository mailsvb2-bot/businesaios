from __future__ import annotations

from application.business_autonomy.channel_contracts import ChannelKind
from application.business_autonomy.contracts import BusinessExecutionRequest, ExecutionVerdict
from application.business_autonomy.execution_subject import business_execution_approval_id
from application.business_autonomy.onboarding_contract import BusinessOnboardingRequest
from entrypoints.api.approval_route_handlers import ApprovalRouteHandlers
from governance.approval_contract import ApprovalOutcome
from governance.rbac_contract import RoleId
from runtime.business_autonomy.bootstrap import (
    build_business_autonomy_admin_dependencies,
    build_business_autonomy_guarded_service,
)


def _channel_identity(business_id: str) -> tuple[ChannelKind, str, str]:
    normalized = str(business_id).strip().lower()
    if "site" in normalized or "web" in normalized:
        return ChannelKind.WEBSITE, "website.default", f"https://{normalized}.example.test"
    if "shop" in normalized or "commerce" in normalized:
        return ChannelKind.COMMERCE, "commerce.default", f"commerce://{normalized}"
    if "bot" in normalized:
        return ChannelKind.CHATBOT, "chatbot.default", f"bot://{normalized}"
    return ChannelKind.API_BUSINESS, "api.default", f"api://{normalized}"


def explicitly_onboard_business(
    *,
    tenant_id: str,
    business_id: str,
    verified_owner: bool = True,
) -> None:
    channel_kind, adapter_key, external_ref = _channel_identity(business_id)
    dependencies = build_business_autonomy_admin_dependencies()
    existing = dependencies["distributed"]["registry"].get(tenant_id, business_id)
    if existing is not None:
        return
    dependencies["onboarding"].onboard(
        BusinessOnboardingRequest(
            business_id=business_id,
            tenant_id=tenant_id,
            ownership_key=f"test-owner:{tenant_id}:{business_id}",
            region="eu-west-1",
            channel_kind=channel_kind,
            adapter_key=adapter_key,
            external_ref=external_ref,
            requested_by="canonical-test-onboarding",
            metadata={
                "verified_owner": bool(verified_owner),
                "non_ai_mode": "supervised",
                "requires_human_approval": not bool(verified_owner),
            },
        )
    )


def build_explicitly_onboarded_service(*, tenant_id: str, business_id: str, verified_owner: bool = True):
    explicitly_onboard_business(
        tenant_id=tenant_id,
        business_id=business_id,
        verified_owner=verified_owner,
    )
    return build_business_autonomy_guarded_service(business_id=business_id)


async def approve_pending_and_execute(
    service,
    request: BusinessExecutionRequest,
    *,
    actor_id: str = "operator-1",
):
    pending = await service.execute(request)
    assert pending.verdict is ExecutionVerdict.PARTIAL
    approval_id = business_execution_approval_id(request)
    open_records = service._approval_gate._store.list_open(
        tenant_id=str(request.envelope.metadata["tenant_id"])
    )
    assert any(record.request.approval_id == approval_id for record in open_records)
    ApprovalRouteHandlers(approval_store=service._approval_gate._store).evaluate(
        approval_id=approval_id,
        tenant_id=str(request.envelope.metadata["tenant_id"]),
        actor_id=actor_id,
        role_id=RoleId.OWNER,
        outcome=ApprovalOutcome.APPROVE,
        rationale="Approved through canonical governance test path.",
    )
    return await service.execute(request)


__all__ = [
    "approve_pending_and_execute",
    "build_explicitly_onboarded_service",
    "explicitly_onboard_business",
]
