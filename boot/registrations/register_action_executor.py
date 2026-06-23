from __future__ import annotations

from boot.registrations._shared import register_runtime_service
from boot.runtime_service_contracts import ActionExecutor
from runtime.registry import RuntimeRegistry
from runtime.service_names import RuntimeServiceName
from runtime.service_types import RuntimeServiceType


def register_action_executor(registry: RuntimeRegistry):
    from boot.factories.action_executor_factory import build_action_executor

    return register_runtime_service(
        registry,
        name=RuntimeServiceName.ACTION_EXECUTOR,
        service=build_action_executor(),
        service_type=RuntimeServiceType.EXECUTOR,
        dependencies=(),
    )


__all__ = ["ActionExecutor", "register_action_executor"]
