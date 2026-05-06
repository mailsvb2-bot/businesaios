from __future__ import annotations
CANON_EXECUTE_ACTION_PORT_PROVIDER_FINAL_OWNER = True


from dataclasses import dataclass
from typing import Protocol

from entrypoints.api.execute_action_api_stack import build_execute_action_api_stack
from observability.action_audit_log import ActionAuditLog


CANON_API_EXECUTE_ACTION_PORT_PROVIDER = True
CANON_API_EXECUTE_ACTION_PORT_PROVIDER_SINGLE_OWNER = True
CANON_API_EXECUTE_ACTION_PORT_PROVIDER_NO_DECISION_LOGIC = True
CANON_API_EXECUTE_ACTION_PORT_PROVIDER_STACK_OWNER = True


class DependencyContainerLike(Protocol):
    tenant_quota_guard: object
    api_idempotency_store: object


class ExecuteActionPortLike(Protocol):
    def handle(self, request, *, request_context=None, idempotency_key=None, action_id=None): ...


@dataclass(frozen=True)
class ExecuteActionPortProvider:
    application_service: object
    dependency_container: DependencyContainerLike | None = None
    action_audit_log: ActionAuditLog | None = None

    def build_port(self) -> ExecuteActionPortLike | None:
        dependency_container = self.dependency_container
        if dependency_container is None:
            return None
        return build_execute_action_api_stack(
            application_service=self.application_service,
            tenant_quota_guard=dependency_container.tenant_quota_guard,
            action_audit_log=self.action_audit_log,
            idempotency_store=dependency_container.api_idempotency_store,
        )



def build_execute_action_port_provider(
    *,
    application_service: object,
    dependency_container: DependencyContainerLike | None = None,
    action_audit_log: ActionAuditLog | None = None,
) -> ExecuteActionPortProvider:
    return ExecuteActionPortProvider(
        application_service=application_service,
        dependency_container=dependency_container,
        action_audit_log=action_audit_log,
    )



def build_execute_action_port(
    *,
    application_service: object,
    dependency_container: DependencyContainerLike | None = None,
    action_audit_log: ActionAuditLog | None = None,
) -> ExecuteActionPortLike | None:
    return build_execute_action_port_provider(
        application_service=application_service,
        dependency_container=dependency_container,
        action_audit_log=action_audit_log,
    ).build_port()


__all__ = [
    'CANON_API_EXECUTE_ACTION_PORT_PROVIDER',
    'CANON_API_EXECUTE_ACTION_PORT_PROVIDER_SINGLE_OWNER',
    'CANON_API_EXECUTE_ACTION_PORT_PROVIDER_NO_DECISION_LOGIC',
    'CANON_API_EXECUTE_ACTION_PORT_PROVIDER_STACK_OWNER',
    'DependencyContainerLike',
    'ExecuteActionPortLike',
    'ExecuteActionPortProvider',
    'build_execute_action_port_provider',
    'build_execute_action_port',
]
