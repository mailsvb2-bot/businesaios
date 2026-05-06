from __future__ import annotations
CANON_EXECUTE_ACTION_AUDIT_PAYLOAD_FINAL_OWNER = True


from typing import Any, Mapping

from entrypoints.api.action_models import ExecuteActionRequest
from entrypoints.api.request_context import RequestContext
from security.payload_redaction import PayloadRedactor


CANON_API_EXECUTE_ACTION_AUDIT_PAYLOAD = True


def build_execute_action_audit_payload(
    *,
    request: ExecuteActionRequest,
    stage: str,
    response_status: str | None = None,
    response_reason: str | None = None,
    request_context: RequestContext | None = None,
    idempotency_key: str | None = None,
    idempotency_storage_key: str | None = None,
    idempotency_resolution: str | None = None,
    replayed: bool | None = None,
    extra_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    redactor = PayloadRedactor()
    payload: dict[str, Any] = {
        'stage': str(stage),
        'request_payload': redactor.redact(dict(request.payload)),
        'response_status': response_status,
        'response_reason': response_reason,
    }
    if request_context is not None:
        payload['request_context'] = request_context.redacted_dict()
    if idempotency_key is not None:
        payload['idempotency_key'] = str(idempotency_key)
    if idempotency_storage_key is not None:
        payload['idempotency_storage_key'] = str(idempotency_storage_key)
    if idempotency_resolution is not None:
        payload['idempotency_resolution'] = str(idempotency_resolution)
    if replayed is not None:
        payload['replayed'] = bool(replayed)
    if extra_payload:
        payload.update(dict(redactor.redact(dict(extra_payload))))
    return payload


__all__ = [
    'CANON_API_EXECUTE_ACTION_AUDIT_PAYLOAD',
    'build_execute_action_audit_payload',
]
