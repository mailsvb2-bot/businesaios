from __future__ import annotations
CANON_EXECUTE_ACTION_WITH_CONTROL_PLANE_FINAL_OWNER = True


from dataclasses import dataclass, field
from typing import Protocol

from infra.runtime_guardrails import RuntimeGuardrails
from entrypoints.api.action_models import ExecuteActionRequest, ExecuteActionResponse
from entrypoints.api.execute_action_audit_payload import build_execute_action_audit_payload
from entrypoints.api.request_context import RequestContext
from entrypoints.api.response_presenter import present_blocked_execute_action_response
from entrypoints.api.signature_binding import supported_kwargs
from observability.action_audit_log import ActionAuditLog
from tenancy.tenant_quota_guard import QuotaDimension, TenantQuotaGuard


CANON_API_EXECUTE_ACTION_WITH_CONTROL_PLANE = True


class ExecuteActionPort(Protocol):
    def handle(self, request: ExecuteActionRequest) -> ExecuteActionResponse: ...


@dataclass(frozen=True)
class ExecuteActionWithControlPlane:
    """
    Thin control-plane envelope around the canonical execute-action handler.

    It may block execution via guardrails/quota and records audit markers, but it
    never plans, rewrites, or chooses actions on its own.
    """

    handler: ExecuteActionPort
    guardrails: RuntimeGuardrails
    tenant_quota_guard: TenantQuotaGuard | None = None
    action_audit_log: ActionAuditLog = field(default_factory=ActionAuditLog)
    quota_dimension: str = QuotaDimension.ACTIONS_PER_HOUR.value
    quota_amount: float = 1.0
    consume_quota_after_success_only: bool = True

    def handle(
        self,
        *,
        request: ExecuteActionRequest,
        request_context: RequestContext | None = None,
        idempotency_key: str | None = None,
        action_id: str | None = None,
    ) -> ExecuteActionResponse:
        resolved_action_id = self._resolve_action_id(
            request=request,
            request_context=request_context,
            action_id=action_id,
        )
        trace_id = self._resolve_trace_id(request_context=request_context)
        tenant_id = self._resolve_tenant_id(
            request=request,
            request_context=request_context,
        )

        idempotency_state = self._handler_idempotency_state(
            request=request,
            request_context=request_context,
            idempotency_key=idempotency_key,
        )
        known_replay = idempotency_state == 'completed'
        known_in_progress = idempotency_state == 'in_progress'

        self._record_audit(
            tenant_id=tenant_id,
            action_id=resolved_action_id,
            trace_id=trace_id,
            request=request,
            request_context=request_context,
            response_status='received',
            response_reason=None,
            stage='control_plane.received',
            extra_payload={
                'known_replay': known_replay,
                'idempotency_state': idempotency_state,
            },
        )

        guardrail_decision = self.guardrails.evaluate(
            operation_name='api.execute_action',
            required_feature_flag='api.execute_action.enabled',
            kill_switch_name='api.execute_action',
            allow_during_maintenance=False,
        )
        if not guardrail_decision.allowed:
            response = present_blocked_execute_action_response(
                action_type=request.action_type,
                reason=';'.join(guardrail_decision.reasons),
                details={
                    'control_plane_stage': 'guardrails_blocked',
                    'guardrail_reasons': list(guardrail_decision.reasons),
                },
            )
            self._record_audit(
                tenant_id=tenant_id,
                action_id=resolved_action_id,
                trace_id=trace_id,
                request=request,
                request_context=request_context,
                response_status=response.status,
                response_reason=response.reason,
                stage='control_plane.guardrails_blocked',
                extra_payload={
                    'guardrail_reasons': list(guardrail_decision.reasons),
                },
            )
            return response

        if self.tenant_quota_guard is not None and tenant_id is not None and not known_replay and not known_in_progress:
            quota_verdict = self.tenant_quota_guard.check(
                tenant_id=tenant_id,
                dimension=self.quota_dimension,
                amount=self.quota_amount,
            )
            if not quota_verdict.allowed:
                response = present_blocked_execute_action_response(
                    action_type=request.action_type,
                    reason=str(quota_verdict.reason or 'quota_exceeded'),
                    details={
                        'control_plane_stage': 'quota_blocked',
                        'quota_dimension': quota_verdict.dimension,
                        'quota_requested': quota_verdict.requested,
                        'quota_used': quota_verdict.used,
                        'quota_limit': quota_verdict.limit,
                        'quota_remaining': quota_verdict.remaining,
                        'retry_after_seconds': quota_verdict.retry_after_seconds,
                    },
                )
                self._record_audit(
                    tenant_id=tenant_id,
                    action_id=resolved_action_id,
                    trace_id=trace_id,
                    request=request,
                    request_context=request_context,
                    response_status=response.status,
                    response_reason=response.reason,
                    stage='control_plane.quota_blocked',
                    extra_payload={
                        'known_replay': known_replay,
                        'idempotency_state': idempotency_state,
                        'quota_dimension': quota_verdict.dimension,
                        'quota_requested': quota_verdict.requested,
                        'quota_used': quota_verdict.used,
                        'quota_limit': quota_verdict.limit,
                        'quota_remaining': quota_verdict.remaining,
                        'retry_after_seconds': quota_verdict.retry_after_seconds,
                    },
                )
                return response
        elif self.tenant_quota_guard is not None and tenant_id is not None and known_replay:
            self._record_audit(
                tenant_id=tenant_id,
                action_id=resolved_action_id,
                trace_id=trace_id,
                request=request,
                request_context=request_context,
                response_status='received',
                response_reason=None,
                stage='control_plane.quota_bypassed_replay',
                extra_payload={
                    'known_replay': True,
                    'idempotency_state': idempotency_state,
                    'quota_dimension': self.quota_dimension,
                    'quota_amount': self.quota_amount,
                },
            )
        elif self.tenant_quota_guard is not None and tenant_id is not None and known_in_progress:
            self._record_audit(
                tenant_id=tenant_id,
                action_id=resolved_action_id,
                trace_id=trace_id,
                request=request,
                request_context=request_context,
                response_status='received',
                response_reason=None,
                stage='control_plane.quota_bypassed_in_progress',
                extra_payload={
                    'known_replay': False,
                    'idempotency_state': idempotency_state,
                    'quota_dimension': self.quota_dimension,
                    'quota_amount': self.quota_amount,
                },
            )

        try:
            response = self._invoke_handler(
                request=request,
                request_context=request_context,
                idempotency_key=idempotency_key,
                action_id=resolved_action_id,
            )
        except Exception as exc:
            self._record_audit(
                tenant_id=tenant_id,
                action_id=resolved_action_id,
                trace_id=trace_id,
                request=request,
                request_context=request_context,
                response_status='error',
                response_reason=f'{type(exc).__name__}:{exc}',
                stage='control_plane.handler_error',
            )
            raise

        if (
            self.tenant_quota_guard is not None
            and tenant_id is not None
            and not known_replay
            and not known_in_progress
            and self.consume_quota_after_success_only
            and self._is_successful(response)
        ):
            consume_verdict = self.tenant_quota_guard.consume(
                tenant_id=tenant_id,
                dimension=self.quota_dimension,
                amount=self.quota_amount,
            )
            self._record_audit(
                tenant_id=tenant_id,
                action_id=resolved_action_id,
                trace_id=trace_id,
                request=request,
                request_context=request_context,
                response_status=response.status,
                response_reason=response.reason,
                stage='control_plane.quota_consumed',
                extra_payload={
                    'quota_dimension': consume_verdict.dimension,
                    'quota_requested': consume_verdict.requested,
                    'quota_used': consume_verdict.used,
                    'quota_limit': consume_verdict.limit,
                    'quota_remaining': consume_verdict.remaining,
                },
            )

        final_stage = 'control_plane.replayed' if known_replay else 'control_plane.executed'
        if response.status == 'blocked' and response.details.get('guard_stage') == 'idempotency_in_progress':
            final_stage = 'control_plane.idempotency_in_progress'
        elif response.status == 'blocked' and response.details.get('guard_stage') == 'idempotency_terminal_failed':
            final_stage = 'control_plane.idempotency_terminal_failed'

        self._record_audit(
            tenant_id=tenant_id,
            action_id=resolved_action_id,
            trace_id=trace_id,
            request=request,
            request_context=request_context,
            response_status=response.status,
            response_reason=response.reason,
            stage=final_stage,
            extra_payload={
                'known_replay': known_replay,
                'idempotency_state': idempotency_state,
            },
        )
        return response

    @staticmethod
    def _is_successful(response: ExecuteActionResponse) -> bool:
        status = str(response.status or '').strip().lower()
        return status not in {'blocked', 'error', 'failed', 'denied'}

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
            return request_context.normalized_request_id()

        return f'api:{request.action_type}'

    @staticmethod
    def _resolve_trace_id(*, request_context: RequestContext | None) -> str | None:
        if request_context is None:
            return None
        return request_context.normalized_correlation_id()

    def _handler_idempotency_state(
        self,
        *,
        request: ExecuteActionRequest,
        request_context: RequestContext | None,
        idempotency_key: str | None,
    ) -> str:
        describe_state = getattr(self.handler, 'idempotency_state', None)
        if callable(describe_state):
            kwargs = supported_kwargs(
                describe_state,
                request=request,
                request_context=request_context,
                idempotency_key=idempotency_key,
            )
            value = str(describe_state(**kwargs)).strip().lower()
            return value or 'missing'

        has_completed = getattr(self.handler, 'has_completed_response', None)
        if not callable(has_completed):
            return 'missing'
        kwargs = supported_kwargs(
            has_completed,
            request=request,
            request_context=request_context,
            idempotency_key=idempotency_key,
        )
        return 'completed' if bool(has_completed(**kwargs)) else 'missing'

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

    def _record_audit(
        self,
        *,
        tenant_id: str | None,
        action_id: str,
        trace_id: str | None,
        request: ExecuteActionRequest,
        request_context: RequestContext | None,
        response_status: str,
        response_reason: str | None,
        stage: str,
        extra_payload: dict[str, object] | None = None,
    ) -> None:
        payload = build_execute_action_audit_payload(
            request=request,
            stage=stage,
            response_status=response_status,
            response_reason=response_reason,
            request_context=request_context,
            extra_payload=extra_payload,
        )

        self.action_audit_log.record_execution(
            tenant_id=str(tenant_id or 'unknown'),
            action_id=action_id,
            action_type=request.action_type,
            status=response_status,
            trace_id=trace_id,
            payload=payload,
        )




def build_execute_action_control_plane(
    *,
    handler: ExecuteActionPort,
    guardrails: RuntimeGuardrails,
    tenant_quota_guard: TenantQuotaGuard | None = None,
    action_audit_log: ActionAuditLog | None = None,
    quota_dimension: str = QuotaDimension.ACTIONS_PER_HOUR.value,
    quota_amount: float = 1.0,
    consume_quota_after_success_only: bool = True,
) -> "ExecuteActionWithControlPlane":
    return ExecuteActionWithControlPlane(
        handler=handler,
        guardrails=guardrails,
        tenant_quota_guard=tenant_quota_guard,
        action_audit_log=action_audit_log or ActionAuditLog(),
        quota_dimension=quota_dimension,
        quota_amount=quota_amount,
        consume_quota_after_success_only=consume_quota_after_success_only,
    )

__all__ = [
    'CANON_API_EXECUTE_ACTION_WITH_CONTROL_PLANE',
    'ExecuteActionPort',
    'ExecuteActionWithControlPlane',
]
