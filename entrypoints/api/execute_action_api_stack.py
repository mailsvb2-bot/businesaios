from __future__ import annotations
CANON_API_EXECUTE_ACTION_STACK_FINAL_OWNER = True


from dataclasses import dataclass

from config.env_flags import env_bool, env_float, env_int, env_str
from infra.feature_flag_store import InMemoryFeatureFlagStore
from infra.feature_flags import FeatureFlags
from infra.idempotency import IdempotencyExecutor
from infra.kill_switches import KillSwitchRegistry
from infra.maintenance_mode import MaintenanceMode
from infra.retry_models import RetryPolicySpec
from infra.retry_policy import RetryPolicy
from infra.runtime_guardrails import RuntimeGuardrails
from entrypoints.api.action_models import ExecuteActionRequest, ExecuteActionResponse
from entrypoints.api.execute_action_idempotency_store import build_api_execute_action_idempotency_store
from entrypoints.api.execute_action_stack_bundle import build_execute_action_stack_bundle
from entrypoints.api.request_context import RequestContext
from observability.action_audit_log import ActionAuditLog, build_default_action_audit_log
from reliability.idempotency_store import InMemoryIdempotencyStore as ReliabilityInMemoryIdempotencyStore
from tenancy.tenant_quota_guard import QuotaDimension, TenantQuotaGuard


CANON_API_EXECUTE_ACTION_STACK = True
CANON_API_EXECUTE_ACTION_STACK_WRAPPER_BUILDERS = True



@dataclass(frozen=True)
class ExecuteActionApiStack:
    """
    Canonical execute-action API stack.

    Ownership is intentionally linear:
    ExecuteActionHandler -> reliability guards -> control-plane envelope.
    Composition remains delegated to the shared execute-action stack bundle.
    This module centralizes composition so route surfaces do not rebuild parallel
    wrapper chains and drift over time.
    """

    control_plane: ExecuteActionWithControlPlane

    def handle(
        self,
        request: ExecuteActionRequest,
        *,
        request_context: RequestContext | None = None,
        idempotency_key: str | None = None,
        action_id: str | None = None,
    ) -> ExecuteActionResponse:
        return self.control_plane.handle(
            request=request,
            request_context=request_context,
            idempotency_key=idempotency_key,
            action_id=action_id,
        )

def build_execute_action_api_stack(
    *,
    application_service: object,
    tenant_quota_guard: TenantQuotaGuard | None = None,
    action_audit_log: ActionAuditLog | None = None,
    idempotency_store: object | None = None,
) -> ExecuteActionApiStack:
    audit_log = action_audit_log or build_default_action_audit_log()
    retry_policy = RetryPolicy(
        spec=RetryPolicySpec(
            max_attempts=env_int('BUSINESAIOS_API_EXECUTE_ACTION_RETRY_ATTEMPTS', 2, lo=1, hi=10),
            delay_seconds=env_float('BUSINESAIOS_API_EXECUTE_ACTION_RETRY_DELAY_SECONDS', 0.0, lo=0.0, hi=60.0),
        )
    )
    stack_bundle = build_execute_action_stack_bundle(
        application_service=application_service,
        retry_policy=retry_policy,
        idempotency=IdempotencyExecutor(store=_idempotency_store_or_default(idempotency_store)),
        action_audit_log=audit_log,
        guardrails=_build_guardrails(),
        tenant_quota_guard=tenant_quota_guard,
        quota_dimension=env_quota_dimension('BUSINESAIOS_API_EXECUTE_ACTION_QUOTA_DIMENSION', QuotaDimension.ACTIONS_PER_HOUR.value),
        quota_amount=env_float('BUSINESAIOS_API_EXECUTE_ACTION_QUOTA_AMOUNT', 1.0, lo=0.0, hi=1_000_000.0),
        consume_quota_after_success_only=env_bool('BUSINESAIOS_API_EXECUTE_ACTION_CONSUME_QUOTA_AFTER_SUCCESS_ONLY', True),
    )
    return stack_bundle.stack


def _idempotency_store_or_default(candidate: object | None):
    adapted = build_api_execute_action_idempotency_store(candidate)
    if adapted is not None:
        return adapted
    return build_api_execute_action_idempotency_store(ReliabilityInMemoryIdempotencyStore())


def _build_guardrails() -> RuntimeGuardrails:
    flags = FeatureFlags(store=InMemoryFeatureFlagStore())
    if env_bool('BUSINESAIOS_API_EXECUTE_ACTION_ENABLED', True):
        flags.enable('api.execute_action.enabled')
    else:
        flags.disable('api.execute_action.enabled')
    kill_switches = KillSwitchRegistry()
    if env_bool('BUSINESAIOS_API_EXECUTE_ACTION_KILL_SWITCH_TRIPPED', False):
        kill_switches.trip('api.execute_action')
    maintenance_mode = MaintenanceMode()
    if env_bool('BUSINESAIOS_API_EXECUTE_ACTION_MAINTENANCE_MODE', False):
        maintenance_mode.enable(reason='BUSINESAIOS_API_EXECUTE_ACTION_MAINTENANCE_MODE')
    return RuntimeGuardrails(
        feature_flags=flags,
        kill_switches=kill_switches,
        maintenance_mode=maintenance_mode,
    )


def env_quota_dimension(name: str, default: str) -> str:
    value = str(env_str(name, default)).strip()
    return value or default


__all__ = [
    'CANON_API_EXECUTE_ACTION_STACK',
    'CANON_API_EXECUTE_ACTION_STACK_WRAPPER_BUILDERS',
    'ExecuteActionApiStack',
    'build_execute_action_api_stack',
]
