from __future__ import annotations

from dataclasses import dataclass

from entrypoints.api.action_models import ExecuteActionRequest, ExecuteActionResponse
from entrypoints.api.execute_action_with_control_plane import ExecuteActionWithControlPlane
from entrypoints.api.request_context import RequestContext

CANON_EXECUTE_ACTION_API_CONTRACTS = True


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

__all__ = ["CANON_EXECUTE_ACTION_API_CONTRACTS", "ExecuteActionApiStack"]
