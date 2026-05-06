from __future__ import annotations
CANON_EXECUTE_ACTION_REQUEST_ENVELOPE_FINAL_OWNER = True


from entrypoints.api.action_models import ExecuteActionRequest
from entrypoints.api.request_context import RequestContext


CANON_API_EXECUTE_ACTION_REQUEST_ENVELOPE = True


def canonicalize_execute_action_request(
    request: ExecuteActionRequest,
    *,
    request_context: RequestContext | None = None,
    idempotency_key: str | None = None,
    action_id: str | None = None,
) -> ExecuteActionRequest:
    payload = dict(request.payload)

    explicit_action_id = str(action_id or '').strip()
    if explicit_action_id:
        payload['action_id'] = explicit_action_id
    else:
        payload_action_id = str(payload.get('action_id') or '').strip()
        if not payload_action_id and request_context is not None:
            payload['action_id'] = request_context.normalized_request_id()

    explicit_idempotency_key = str(idempotency_key or '').strip()
    if explicit_idempotency_key:
        payload['idempotency_key'] = explicit_idempotency_key
    else:
        payload_idempotency_key = str(payload.get('idempotency_key') or '').strip()
        if not payload_idempotency_key and request_context is not None:
            payload['idempotency_key'] = request_context.normalized_request_id()

    if request_context is not None:
        tenant_id = request_context.validated_tenant_id(required=False)
        if tenant_id and not str(payload.get('tenant_id') or '').strip():
            payload['tenant_id'] = tenant_id

    return ExecuteActionRequest(
        action_type=request.action_type,
        payload=payload,
    )


__all__ = [
    'CANON_API_EXECUTE_ACTION_REQUEST_ENVELOPE',
    'canonicalize_execute_action_request',
]
