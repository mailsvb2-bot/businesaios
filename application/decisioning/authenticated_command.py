"""Authenticated explicit-command binding for the public execute-action API.

This is not a recommendation engine and not a second DecisionCore.  The API
security perimeter has already authenticated and authorized one explicit human
or service command.  This boundary only binds that command to immutable
identity coordinates and signs the canonical DecisionCommand envelope.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from application.decisioning.decision_command import DecisionCommand
from entrypoints.api.request_context import RequestContext
from kernel.decisioning.route_contract import EXPECTED_ISSUER_ID, DecisionRouteViolation

CANON_AUTHENTICATED_DECISION_COMMAND_BINDING = True
CANON_AUTHENTICATED_COMMAND_NO_SELECTION = True
CANON_AUTHENTICATED_COMMAND_NO_EXECUTION = True


def _system_clock_ms() -> int:
    return int(time.time() * 1000)


def _stable_state_hash(*, action: str, payload: Mapping[str, Any], context: RequestContext) -> str:
    body = {
        "action": str(action),
        "payload": dict(payload),
        "tenant_id": context.validated_tenant_id(required=True),
        "actor_id": str(context.actor_id or ""),
        "subject": str(context.subject or ""),
        "correlation_id": context.normalized_correlation_id(),
    }
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AuthenticatedDecisionCommandBinding:
    keyring: Any
    clock_ms: Callable[[], int] = _system_clock_ms
    ttl_ms: int = 5 * 60 * 1000

    def signed_envelope(
        self,
        *,
        action: str,
        payload: Mapping[str, Any],
        request_context: RequestContext,
        action_id: str,
    ) -> Any:
        if request_context.metadata.get("authenticated_principal") is not True:
            raise DecisionRouteViolation("authenticated principal proof is required")
        tenant_id = request_context.validated_tenant_id(required=True)
        actor_id = str(request_context.actor_id or request_context.subject or "").strip()
        if not actor_id:
            raise DecisionRouteViolation("authenticated actor_id is required")
        normalized_action = str(action or "").strip()
        normalized_action_id = str(action_id or "").strip()
        if not normalized_action:
            raise DecisionRouteViolation("action is required")
        if not normalized_action_id:
            raise DecisionRouteViolation("action_id is required")

        issued_at_ms = int(self.clock_ms())
        correlation_id = request_context.normalized_correlation_id()
        request_id = request_context.normalized_request_id()
        command_payload = dict(payload)
        command_payload.update(
            {
                "tenant_id": tenant_id,
                "actor_id": actor_id,
                "subject": str(request_context.subject or ""),
                "request_id": request_id,
                "correlation_id": correlation_id,
                "action_id": normalized_action_id,
                "command_source": "authenticated_api",
            }
        )
        command = DecisionCommand(
            decision_id=f"api-command:{tenant_id}:{normalized_action_id}",
            correlation_id=correlation_id,
            issuer_id=EXPECTED_ISSUER_ID,
            action=normalized_action,
            payload=command_payload,
            snapshot_id=request_id,
            state_hash=_stable_state_hash(
                action=normalized_action,
                payload=command_payload,
                context=request_context,
            ),
            policy_id="authenticated-api-command@v1",
            issued_at_ms=issued_at_ms,
            expires_at_ms=issued_at_ms + max(1, int(self.ttl_ms)),
        )
        return command.to_signed_envelope(self.keyring)


__all__ = [
    "AuthenticatedDecisionCommandBinding",
    "CANON_AUTHENTICATED_COMMAND_NO_EXECUTION",
    "CANON_AUTHENTICATED_COMMAND_NO_SELECTION",
    "CANON_AUTHENTICATED_DECISION_COMMAND_BINDING",
]
