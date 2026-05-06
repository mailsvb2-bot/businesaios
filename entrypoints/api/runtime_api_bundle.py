from __future__ import annotations

from dataclasses import dataclass

from entrypoints.api.api_handler_bundle import ApiHandlerBundle, build_api_handler_bundle
from adapters.api.runtime_api_adapter import RuntimeApiAdapter, build_runtime_api_adapter
from observability.action_audit_log import ActionAuditLog
from runtime.execution.execution_path_lock import build_execution_path_lock_spec


CANON_API_RUNTIME_BUNDLE_SINGLE_OWNER = True
CANON_API_RUNTIME_BUNDLE_NO_DECISION_LOGIC = True


@dataclass(frozen=True)
class RuntimeApiBundle:
    runtime_adapter: RuntimeApiAdapter
    handler_bundle: ApiHandlerBundle
    execution_path_lock: object


def build_runtime_api_bundle(
    *,
    application_service: object,
    dependency_container: object | None = None,
    action_audit_log: ActionAuditLog | None = None,
    handler_bundle: ApiHandlerBundle | None = None,
) -> RuntimeApiBundle:
    return RuntimeApiBundle(
        runtime_adapter=build_runtime_api_adapter(application_service=application_service),
        handler_bundle=handler_bundle or build_api_handler_bundle(
            application_service=application_service,
            dependency_container=dependency_container,
            action_audit_log=action_audit_log,
        ),
        execution_path_lock=build_execution_path_lock_spec(),
    )


__all__ = [
    'CANON_API_RUNTIME_BUNDLE_SINGLE_OWNER',
    'CANON_API_RUNTIME_BUNDLE_NO_DECISION_LOGIC',
    'RuntimeApiBundle',
    'build_runtime_api_bundle',
]
