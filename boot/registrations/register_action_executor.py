from __future__ import annotations

from dataclasses import dataclass, field

from boot.registrations._shared import register_runtime_service
from runtime.constructor_tokens import is_valid_runtime_construction_token
from runtime.registry import RuntimeRegistry
from runtime.sealed_types import SealedType
from runtime.service_names import RuntimeServiceName
from runtime.service_types import RuntimeServiceType


@dataclass
class ActionExecutor(SealedType):
    _construction_token: object = field(repr=False)

    def __post_init__(self) -> None:
        if not is_valid_runtime_construction_token(self._construction_token):
            raise RuntimeError(
                "Illegal ActionExecutor construction. Use canonical boot factory path."
            )

    def execute(self, action: object) -> dict:
        return {
            "status": "accepted",
            "action_type": type(action).__name__,
        }


def register_action_executor(registry: RuntimeRegistry):
    from boot.factories import build_action_executor

    return register_runtime_service(
        registry,
        name=RuntimeServiceName.ACTION_EXECUTOR,
        service=build_action_executor(),
        service_type=RuntimeServiceType.EXECUTOR,
        dependencies=(),
    )
