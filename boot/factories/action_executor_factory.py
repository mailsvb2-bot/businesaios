from __future__ import annotations

from boot.runtime_service_contracts import ActionExecutor
from runtime.constructor_tokens import runtime_construction_token


def build_action_executor() -> ActionExecutor:
    return ActionExecutor(_construction_token=runtime_construction_token())


__all__ = ["build_action_executor"]
