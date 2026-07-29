from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from entrypoints.api.action_mapper import map_execute_action_request
from entrypoints.api.request_context import RequestContext
from entrypoints.api.action_models import ExecuteActionRequest, ExecuteActionResponse
from entrypoints.api.execute_action_request_envelope import canonicalize_execute_action_request
from entrypoints.api.response_presenter import present_execute_action_response
from entrypoints.api.signature_binding import supported_kwargs

CANON_EXECUTE_ACTION_HANDLER_FINAL_OWNER = True
CANON_API_EXECUTE_ACTION_HANDLER_OWNER = True
CANON_API_EXECUTE_ACTION_ENVELOPE_ONLY = True


def build_execute_action_handler(
    *,
    application_service: object,
    command_binding: object | None = None,
) -> "ExecuteActionHandler":
    return ExecuteActionHandler(
        application_service=application_service,
        command_binding=command_binding,
    )


@dataclass(frozen=True)
class ExecuteActionHandler:
    application_service: object
    command_binding: object | None = None

    def handle(
        self,
        request: ExecuteActionRequest,
        *,
        request_context: RequestContext | None = None,
        idempotency_key: str | None = None,
        action_id: str | None = None,
    ) -> ExecuteActionResponse:
        canonical_request = canonicalize_execute_action_request(
            request,
            request_context=request_context,
            idempotency_key=idempotency_key,
            action_id=action_id,
        )
        canonical_action = map_execute_action_request(canonical_request)
        envelope = self._bind_authenticated_envelope(
            action=canonical_action,
            request_context=request_context,
        )
        result = self._invoke_application_service(
            envelope=envelope,
            request_context=request_context,
            idempotency_key=str(canonical_request.payload.get('idempotency_key') or '').strip() or None,
            action_id=str(canonical_request.payload.get('action_id') or '').strip() or None,
        )
        if isinstance(result, Mapping) and not str(result.get('action_type') or '').strip():
            result = {**dict(result), 'action_type': canonical_action.action_type}
        return present_execute_action_response(result)

    def _bind_authenticated_envelope(
        self,
        *,
        action: object,
        request_context: RequestContext | None,
    ) -> object:
        if request_context is None:
            raise PermissionError('authenticated_request_context_required')
        binding = self.command_binding
        signed_envelope = getattr(binding, 'signed_envelope', None)
        if not callable(signed_envelope):
            raise RuntimeError('authenticated_decision_command_binding_not_wired')
        payload = dict(getattr(action, 'payload', {}) or {})
        return signed_envelope(
            action=str(getattr(action, 'action_type', '') or ''),
            payload=payload,
            request_context=request_context,
            action_id=str(payload.get('action_id') or ''),
        )

    def _invoke_application_service(
        self,
        *,
        envelope: object,
        request_context: RequestContext | None,
        idempotency_key: str | None,
        action_id: str | None,
    ) -> object:
        execute_action = self.application_service.execute_action
        tenant_id = None
        if request_context is not None:
            tenant_id = request_context.validated_tenant_id(required=False)
        kwargs = supported_kwargs(
            execute_action,
            action=envelope,
            envelope=envelope,
            request_context=request_context,
            idempotency_key=idempotency_key,
            action_id=action_id,
            tenant_id=tenant_id,
        )
        return execute_action(**kwargs)


__all__ = [
    "CANON_API_EXECUTE_ACTION_ENVELOPE_ONLY",
    "CANON_API_EXECUTE_ACTION_HANDLER_OWNER",
    "ExecuteActionHandler",
    "build_execute_action_handler",
]
