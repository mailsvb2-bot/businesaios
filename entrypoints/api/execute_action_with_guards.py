from __future__ import annotations
CANON_EXECUTE_ACTION_WITH_GUARDS_FINAL_OWNER = True


from dataclasses import dataclass, field
from typing import Protocol

from infra.idempotency import IdempotencyExecutor, IdempotencyInProgressError, IdempotencyTerminalFailureError
from infra.retry_policy import RetryPolicy
from entrypoints.api.action_models import ExecuteActionRequest, ExecuteActionResponse
from entrypoints.api.execute_action_audit_payload import build_execute_action_audit_payload
from entrypoints.api.request_context import RequestContext
from entrypoints.api.response_presenter import present_blocked_execute_action_response
from entrypoints.api.signature_binding import supported_kwargs, supports_keyword
from observability.action_audit_log import ActionAuditLog


CANON_API_EXECUTE_ACTION_WITH_GUARDS = True


class ExecuteActionPort(Protocol):
    def handle(
        self,
        request: ExecuteActionRequest,
        *,
        request_context: RequestContext | None = None,
        idempotency_key: str | None = None,
        action_id: str | None = None,
    ) -> ExecuteActionResponse: ...


@dataclass(frozen=True)
class ExecuteActionWithGuards:
    """
    Reliability envelope for the canonical execute-action path.

    This wrapper is limited to idempotency, retry, and audit markers.
    It must not become a second action execution engine.
    """

    handler: ExecuteActionPort
    retry_policy: RetryPolicy
    idempotency: IdempotencyExecutor
    action_audit_log: ActionAuditLog = field(default_factory=ActionAuditLog)

    def has_completed_response(
        self,
        *,
        request: ExecuteActionRequest,
        idempotency_key: str | None = None,
        request_context: RequestContext | None = None,
    ) -> bool:
        return self.idempotency_state(
            request=request,
            idempotency_key=idempotency_key,
            request_context=request_context,
        ) == 'completed'

    def idempotency_state(
        self,
        *,
        request: ExecuteActionRequest,
        idempotency_key: str | None = None,
        request_context: RequestContext | None = None,
    ) -> str:
        tenant_id = self._resolve_tenant_id(request=request, request_context=request_context)
        resolved_key = self._resolve_idempotency_key(
            request=request,
            idempotency_key=idempotency_key,
            request_context=request_context,
        )
        storage_key = self._storage_idempotency_key(idempotency_key=resolved_key, tenant_id=tenant_id)
        return self.idempotency.status(key=storage_key)

    def handle(
        self,
        *,
        request: ExecuteActionRequest,
        idempotency_key: str | None = None,
        request_context: RequestContext | None = None,
        action_id: str | None = None,
    ) -> ExecuteActionResponse:
        tenant_id = self._resolve_tenant_id(
            request=request,
            request_context=request_context,
        )
        resolved_key = self._resolve_idempotency_key(
            request=request,
            idempotency_key=idempotency_key,
            request_context=request_context,
        )
        storage_key = self._storage_idempotency_key(idempotency_key=resolved_key, tenant_id=tenant_id)
        resolved_action_id = self._resolve_action_id(
            request=request,
            request_context=request_context,
            action_id=action_id,
        )
        trace_id = self._resolve_trace_id(request_context=request_context)

        idempotency_state = self.idempotency.status(key=storage_key)
        replayed = idempotency_state == 'completed'
        idempotency_resolution = 'replay_completed' if replayed else 'accepted'

        self.action_audit_log.record_execution(
            tenant_id=str(tenant_id or 'unknown'),
            action_id=resolved_action_id,
            action_type=request.action_type,
            status='guarded_received',
            trace_id=trace_id,
            payload=build_execute_action_audit_payload(
                request=request,
                stage='guards.received',
                request_context=request_context,
                idempotency_key=resolved_key,
                idempotency_storage_key=storage_key,
                idempotency_resolution=idempotency_resolution,
                replayed=replayed,
                extra_payload={
                    'retry_policy': {
                        'max_attempts': int(self.retry_policy.spec.max_attempts),
                        'delay_seconds': float(self.retry_policy.spec.delay_seconds),
                    },
                },
            ),
        )

        try:
            response = self.idempotency.run(
                key=storage_key,
                fn=lambda: self.retry_policy.run(
                    lambda: self._invoke_handler(
                        request=request,
                        request_context=request_context,
                        idempotency_key=resolved_key,
                        action_id=resolved_action_id,
                    )
                ),
            )
        except IdempotencyInProgressError:
            response = present_blocked_execute_action_response(
                action_type=request.action_type,
                reason='idempotency_in_progress',
                details={
                    'guard_stage': 'idempotency_in_progress',
                    'idempotency_key': resolved_key,
                    'idempotency_storage_key': storage_key,
                },
            )
            self.action_audit_log.record_execution(
                tenant_id=str(tenant_id or 'unknown'),
                action_id=resolved_action_id,
                action_type=request.action_type,
                status=response.status,
                trace_id=trace_id,
                payload=build_execute_action_audit_payload(
                    request=request,
                    stage='guards.idempotency_in_progress',
                    response_status=response.status,
                    response_reason=response.reason,
                    request_context=request_context,
                    idempotency_key=resolved_key,
                    idempotency_storage_key=storage_key,
                    idempotency_resolution='rejected_in_progress',
                    replayed=False,
                    extra_payload={
                        'guarded': True,
                    },
                ),
            )
            return response
        except IdempotencyTerminalFailureError as exc:
            response = present_blocked_execute_action_response(
                action_type=request.action_type,
                reason='idempotency_terminal_failed',
                details={
                    'guard_stage': 'idempotency_terminal_failed',
                    'idempotency_key': resolved_key,
                    'idempotency_storage_key': storage_key,
                    'failure_reason': exc.reason,
                },
            )
            self.action_audit_log.record_execution(
                tenant_id=str(tenant_id or 'unknown'),
                action_id=resolved_action_id,
                action_type=request.action_type,
                status=response.status,
                trace_id=trace_id,
                payload=build_execute_action_audit_payload(
                    request=request,
                    stage='guards.idempotency_terminal_failed',
                    response_status=response.status,
                    response_reason=response.reason,
                    request_context=request_context,
                    idempotency_key=resolved_key,
                    idempotency_storage_key=storage_key,
                    idempotency_resolution='rejected_terminal_failed',
                    replayed=False,
                    extra_payload={
                        'guarded': True,
                        'failure_reason': exc.reason,
                    },
                ),
            )
            return response
        except Exception as exc:
            self.action_audit_log.record_execution(
                tenant_id=str(tenant_id or 'unknown'),
                action_id=resolved_action_id,
                action_type=request.action_type,
                status='guarded_error',
                trace_id=trace_id,
                payload=build_execute_action_audit_payload(
                    request=request,
                    stage='guards.error',
                    request_context=request_context,
                    idempotency_key=resolved_key,
                    idempotency_storage_key=storage_key,
                    idempotency_resolution=idempotency_resolution,
                    replayed=replayed,
                    extra_payload={
                        'error_type': type(exc).__name__,
                        'error_message': str(exc),
                    },
                ),
            )
            raise

        self.action_audit_log.record_execution(
            tenant_id=str(tenant_id or 'unknown'),
            action_id=resolved_action_id,
            action_type=request.action_type,
            status=response.status,
            trace_id=trace_id,
            payload=build_execute_action_audit_payload(
                request=request,
                stage='guards.replayed' if replayed else 'guards.executed',
                response_status=response.status,
                response_reason=response.reason,
                request_context=request_context,
                idempotency_key=resolved_key,
                idempotency_storage_key=storage_key,
                idempotency_resolution=idempotency_resolution,
                replayed=replayed,
                extra_payload={'guarded': True},
            ),
        )
        return response

    @staticmethod
    def _resolve_idempotency_key(
        *,
        request: ExecuteActionRequest,
        idempotency_key: str | None,
        request_context: RequestContext | None,
    ) -> str:
        explicit = str(idempotency_key or '').strip()
        if explicit:
            return explicit

        payload_value = request.payload.get('idempotency_key')
        if payload_value is not None and str(payload_value).strip():
            return str(payload_value).strip()

        if request_context is not None:
            request_id = request_context.normalized_request_id()
            if request_id:
                return request_id
            correlation_id = request_context.normalized_correlation_id()
            if correlation_id:
                return correlation_id

        raise ValueError(
            'idempotency_key is required; provide it explicitly, '
            "in payload['idempotency_key'], or via RequestContext.request_id / correlation_id"
        )

    @staticmethod
    def _resolve_action_id(
        *,
        request: ExecuteActionRequest,
        request_context: RequestContext | None,
        action_id: str | None,
    ) -> str:
        explicit = str(action_id or '').strip()
        if explicit:
            return explicit

        payload_action_id = request.payload.get('action_id')
        if payload_action_id is not None and str(payload_action_id).strip():
            return str(payload_action_id).strip()

        if request_context is not None:
            request_id = request_context.normalized_request_id()
            if request_id:
                return request_id

        return f'api:{request.action_type}'

    @staticmethod
    def _storage_idempotency_key(*, idempotency_key: str, tenant_id: str | None) -> str:
        prefix = str(tenant_id or 'global').strip() or 'global'
        return f'{prefix}::{str(idempotency_key).strip()}'

    def _invoke_handler(
        self,
        *,
        request: ExecuteActionRequest,
        request_context: RequestContext | None,
        idempotency_key: str | None,
        action_id: str | None,
    ) -> ExecuteActionResponse:
        handle = self.handler.handle
        kwargs = supported_kwargs(
            handle,
            request=request,
            request_context=request_context,
            idempotency_key=idempotency_key,
            action_id=action_id,
        )
        return handle(**kwargs)

    @staticmethod
    def _resolve_trace_id(*, request_context: RequestContext | None) -> str | None:
        if request_context is None:
            return None
        return request_context.normalized_correlation_id()

    @staticmethod
    def _resolve_tenant_id(
        *,
        request: ExecuteActionRequest,
        request_context: RequestContext | None,
    ) -> str | None:
        if request_context is not None:
            tenant_id = request_context.validated_tenant_id(required=False)
            if tenant_id:
                return tenant_id

        payload_tenant_id = request.payload.get('tenant_id')
        if payload_tenant_id is None:
            return None
        text = str(payload_tenant_id).strip()
        return text or None




def build_execute_action_guarded_handler(
    *,
    handler: ExecuteActionPort,
    retry_policy: RetryPolicy,
    idempotency: IdempotencyExecutor,
    action_audit_log: ActionAuditLog,
) -> "ExecuteActionWithGuards":
    return ExecuteActionWithGuards(
        handler=handler,
        retry_policy=retry_policy,
        idempotency=idempotency,
        action_audit_log=action_audit_log,
    )

__all__ = [
    'CANON_API_EXECUTE_ACTION_WITH_GUARDS',
    'ExecuteActionPort',
    'ExecuteActionWithGuards',
]
