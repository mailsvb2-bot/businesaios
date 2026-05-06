from __future__ import annotations
CANON_EXECUTE_ACTION_HANDLER_FINAL_OWNER = True


from dataclasses import dataclass


from entrypoints.api.action_mapper import map_execute_action_request
from entrypoints.api.request_context import RequestContext
from entrypoints.api.action_models import ExecuteActionRequest, ExecuteActionResponse
from entrypoints.api.execute_action_request_envelope import canonicalize_execute_action_request
from entrypoints.api.response_presenter import present_execute_action_response
from entrypoints.api.signature_binding import supported_kwargs


CANON_API_EXECUTE_ACTION_HANDLER_OWNER = True


def build_execute_action_handler(*, application_service: object) -> "ExecuteActionHandler":
    return ExecuteActionHandler(application_service=application_service)


@dataclass(frozen=True)
class ExecuteActionHandler:
    application_service: object

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
        result = self._invoke_application_service(
            action=canonical_action,
            request_context=request_context,
            idempotency_key=str(canonical_request.payload.get('idempotency_key') or '').strip() or None,
            action_id=str(canonical_request.payload.get('action_id') or '').strip() or None,
        )
        return present_execute_action_response(result)

    def _invoke_application_service(
        self,
        *,
        action: object,
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
            action=action,
            request_context=request_context,
            idempotency_key=idempotency_key,
            action_id=action_id,
            tenant_id=tenant_id,
        )
        return execute_action(**kwargs)


__all__ = [
    "CANON_API_EXECUTE_ACTION_HANDLER_OWNER",
    "ExecuteActionHandler",
    "build_execute_action_handler",
]
