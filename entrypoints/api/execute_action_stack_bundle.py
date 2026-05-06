from __future__ import annotations
CANON_EXECUTE_ACTION_STACK_BUNDLE_FINAL_OWNER = True


from dataclasses import dataclass

from entrypoints.api.execute_action_handler import ExecuteActionHandler, build_execute_action_handler
from entrypoints.api.execute_action_with_control_plane import ExecuteActionWithControlPlane, build_execute_action_control_plane
from entrypoints.api.execute_action_with_guards import ExecuteActionWithGuards, build_execute_action_guarded_handler
from observability.action_audit_log import ActionAuditLog
from infra.idempotency import IdempotencyExecutor
from runtime.execution.execution_path_lock import build_execution_path_lock_spec
from infra.retry_policy import RetryPolicy
from infra.runtime_guardrails import RuntimeGuardrails
from tenancy.tenant_quota_guard import TenantQuotaGuard


CANON_API_EXECUTE_ACTION_STACK_BUNDLE_OWNER = True
CANON_API_EXECUTE_ACTION_STACK_BUNDLE_NO_DECISION_LOGIC = True


@dataclass(frozen=True)
class ExecuteActionStackBundle:
    handler: ExecuteActionHandler
    guarded_handler: ExecuteActionWithGuards
    control_plane: ExecuteActionWithControlPlane
    stack: object
    execution_path_lock: object


def build_execute_action_stack_bundle(
    *,
    application_service: object,
    retry_policy: RetryPolicy,
    idempotency: IdempotencyExecutor,
    action_audit_log: ActionAuditLog,
    guardrails: RuntimeGuardrails,
    tenant_quota_guard: TenantQuotaGuard | None = None,
    quota_dimension: str,
    quota_amount: float,
    consume_quota_after_success_only: bool,
) -> ExecuteActionStackBundle:
    handler = build_execute_action_handler(application_service=application_service)
    guarded_handler = build_execute_action_guarded_handler(
        handler=handler,
        retry_policy=retry_policy,
        idempotency=idempotency,
        action_audit_log=action_audit_log,
    )
    control_plane = build_execute_action_control_plane(
        handler=guarded_handler,
        guardrails=guardrails,
        tenant_quota_guard=tenant_quota_guard,
        action_audit_log=action_audit_log,
        quota_dimension=quota_dimension,
        quota_amount=quota_amount,
        consume_quota_after_success_only=consume_quota_after_success_only,
    )
    return ExecuteActionStackBundle(
        handler=handler,
        guarded_handler=guarded_handler,
        control_plane=control_plane,
        stack=_build_execute_action_api_stack(control_plane=control_plane),
        execution_path_lock=build_execution_path_lock_spec(),
    )


def _build_execute_action_api_stack(*, control_plane: ExecuteActionWithControlPlane) -> object:
    from entrypoints.api.execute_action_api_stack import ExecuteActionApiStack
    return ExecuteActionApiStack(control_plane=control_plane)

__all__ = [
    "CANON_API_EXECUTE_ACTION_STACK_BUNDLE_OWNER",
    "CANON_API_EXECUTE_ACTION_STACK_BUNDLE_NO_DECISION_LOGIC",
    "ExecuteActionStackBundle",
    "build_execute_action_stack_bundle",
]
