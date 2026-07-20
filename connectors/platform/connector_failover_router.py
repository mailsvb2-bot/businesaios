from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from time import monotonic

from connectors.platform.connector_circuit_breaker import ConnectorCircuitBreaker
from connectors.platform.connector_contract import ConnectorRequest, ConnectorVerificationRequest
from connectors.platform.connector_fallback_router import plan_connector_candidates
from connectors.platform.connector_health_monitor import ConnectorHealthMonitor, ConnectorHealthSample
from connectors.platform.connector_observability import ConnectorExecutionEvent, ConnectorObservability
from connectors.platform.connector_registry import ConnectorRegistry, ConnectorRegistryEntry
from connectors.platform.connector_retry_policy import ConnectorRetryPolicy, RetryClassification, RetryContext
from connectors.platform.connector_timeout_policy import ConnectorTimeoutPolicy
from connectors.platform.connector_version_registry import ConnectorVersionRegistry
from interfaces.common.connector_result import ConnectorResult

CANON_CONNECTOR_FAILOVER_ROUTER = True

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConnectorRouteAttempt:
    connector_id: str
    provider: str
    version: str
    operation: str
    route_index: int
    attempt: int
    phase: str
    outcome: str
    reason: str
    duration_ms: float
    breaker_state: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ConnectorFailoverResult:
    result: ConnectorResult
    connector_id: str
    provider: str
    version: str
    operation: str
    fallback_depth: int
    attempts: tuple[ConnectorRouteAttempt, ...] = field(default_factory=tuple)


class ConnectorFailoverRouter:
    def __init__(self, *, registry: ConnectorRegistry, version_registry: ConnectorVersionRegistry | None = None, health_monitor: ConnectorHealthMonitor | None = None, circuit_breaker: ConnectorCircuitBreaker | None = None, retry_policy: ConnectorRetryPolicy | None = None, timeout_policy: ConnectorTimeoutPolicy | None = None, observability: ConnectorObservability | None = None, sleep_fn: Callable[[RetryClassification], None] | None = None, allow_replacement_version_failover: bool = False) -> None:
        self._registry = registry
        self._version_registry = version_registry
        self._health_monitor = health_monitor
        self._circuit_breaker = circuit_breaker
        self._retry_policy = retry_policy or ConnectorRetryPolicy()
        self._timeout_policy = timeout_policy or ConnectorTimeoutPolicy()
        self._observability = observability
        self._sleep = sleep_fn or self._retry_policy.maybe_sleep
        self._allow_replacement_version_failover = bool(allow_replacement_version_failover)

    def execute(self, request: ConnectorRequest, *, requested_version: str | None = None, preferred_provider: str | None = None, require_write: bool = False, failover_on_result_codes: tuple[str, ...] = ('timeout', 'transport_error', 'temporarily_unavailable', 'upstream_5xx', 'rate_limited', 'throttled', 'connector_unavailable')) -> ConnectorFailoverResult:
        request.validate()
        return self._run(
            tenant_id=request.tenant_id,
            connector_id=request.connector_id,
            operation=request.operation,
            requested_version=requested_version,
            preferred_provider=preferred_provider,
            require_write=require_write,
            require_verify=False,
            dry_run=bool(request.dry_run),
            timeout_seconds=request.timeout_seconds,
            trace_id=request.trace_id,
            retry_context=RetryContext(operation=request.operation, write=bool(require_write), verify=False, dry_run=bool(request.dry_run), idempotency_key_present=bool(str(request.idempotency_key or '').strip())),
            call=lambda entry: entry.connector.execute(request),
            phase='execute',
            failover_on_result_codes=failover_on_result_codes,
        )

    def verify(self, request: ConnectorVerificationRequest, *, requested_version: str | None = None, preferred_provider: str | None = None) -> ConnectorFailoverResult:
        request.validate()
        return self._run(
            tenant_id=request.tenant_id,
            connector_id=request.connector_id,
            operation=request.operation,
            requested_version=requested_version,
            preferred_provider=preferred_provider,
            require_write=False,
            require_verify=True,
            dry_run=False,
            timeout_seconds=None,
            trace_id=request.trace_id,
            retry_context=RetryContext(operation=request.operation, write=False, verify=True, dry_run=False, idempotency_key_present=True),
            call=lambda entry: entry.connector.verify(request),
            phase='verify',
            failover_on_result_codes=('timeout', 'transport_error', 'temporarily_unavailable', 'upstream_5xx', 'rate_limited', 'throttled', 'connector_unavailable', 'verify_failed_transient'),
        )

    def _run(self, *, tenant_id: str, connector_id: str, operation: str, requested_version: str | None, preferred_provider: str | None, require_write: bool, require_verify: bool, dry_run: bool, timeout_seconds: float | None, trace_id: str | None, retry_context: RetryContext, call: Callable[[ConnectorRegistryEntry], ConnectorResult], phase: str, failover_on_result_codes: tuple[str, ...]) -> ConnectorFailoverResult:
        candidates = plan_connector_candidates(registry=self._registry, version_registry=self._version_registry, connector_id=connector_id, operation=operation, requested_version=requested_version, preferred_provider=preferred_provider, require_write=require_write, require_verify=require_verify, allow_replacement_version_failover=self._allow_replacement_version_failover)
        if not candidates:
            raise RuntimeError(f'no connector candidates for connector_id={connector_id} operation={operation}')
        attempts: list[ConnectorRouteAttempt] = []
        last_non_ok_result: tuple[ConnectorResult, ConnectorRegistryEntry, int] | None = None
        last_exception: Exception | None = None
        prior_call_attempted = False
        for route_index, entry in enumerate(candidates):
            if not self._route_safe_for_request(entry=entry, route_index=route_index, requested_version=requested_version, retry_context=retry_context, prior_call_attempted=prior_call_attempted):
                attempts.append(self._attempt_row(entry=entry, operation=operation, route_index=route_index, attempt=0, phase=phase, outcome='skipped', reason='unsafe_failover_route', duration_ms=0.0, breaker_state=None, metadata={'write': retry_context.write, 'dry_run': retry_context.dry_run}))
                self._record_observability(tenant_id=tenant_id, entry=entry, operation=operation, phase=phase, status='unsafe_failover_route', trace_id=trace_id, duration_ms=0.0, fallback_depth=route_index, payload={'reason': 'unsafe_failover_route', 'route_index': route_index, 'attempt': 0, 'write': retry_context.write, 'dry_run': retry_context.dry_run, 'breaker_state': None})
                continue
            if self._health_monitor is not None:
                verdict = self._health_monitor.verdict(connector_id=entry.connector_id, version=entry.version, provider=entry.provider, probe_if_missing=True)
                if not verdict.healthy:
                    attempts.append(self._attempt_row(entry=entry, operation=operation, route_index=route_index, attempt=0, phase=phase, outcome='skipped', reason=str(verdict.reason or 'connector_unhealthy'), duration_ms=0.0, breaker_state=None, metadata={'health_reason': verdict.reason, 'stale': verdict.stale}))
                    self._record_observability(tenant_id=tenant_id, entry=entry, operation=operation, phase=phase, status='skipped_unhealthy', trace_id=trace_id, duration_ms=0.0, fallback_depth=route_index, payload={'reason': verdict.reason, 'route_index': route_index, 'attempt': 0, 'breaker_state': None})
                    continue
            permit_state = None
            if self._circuit_breaker is not None:
                permit = self._circuit_breaker.allow_call(connector_id=entry.connector_id, provider=entry.provider, version=entry.version, operation=operation)
                permit_state = permit.state
                if not permit.allowed:
                    attempts.append(self._attempt_row(entry=entry, operation=operation, route_index=route_index, attempt=0, phase=phase, outcome='blocked', reason=permit.reason, duration_ms=0.0, breaker_state=permit.state, metadata={'blocked_until': permit.blocked_until}))
                    self._record_observability(tenant_id=tenant_id, entry=entry, operation=operation, phase=phase, status='blocked', trace_id=trace_id, duration_ms=0.0, fallback_depth=route_index, payload={'reason': permit.reason, 'blocked_until': permit.blocked_until, 'route_index': route_index, 'attempt': 0, 'breaker_state': permit.state})
                    continue
            rule = self._retry_policy.resolve_rule(operation=operation)
            max_attempts = int(rule.max_attempts)
            if max_attempts <= 0:
                raise ValueError('connector retry max_attempts must be > 0')
            attempt_no = 1
            while True:
                started = monotonic()
                prior_call_attempted = True
                try:
                    result = self._timeout_policy.run(lambda entry=entry: call(entry), operation=operation, verify=bool(retry_context.verify), dry_run=bool(dry_run), requested_timeout=timeout_seconds)
                except Exception as exc:
                    duration_ms = (monotonic() - started) * 1000.0
                    classification = self._retry_policy.classify_exception(context=retry_context, error=exc, attempt=attempt_no)
                    attempts.append(self._attempt_row(entry=entry, operation=operation, route_index=route_index, attempt=attempt_no, phase=phase, outcome='exception', reason=classification.reason, duration_ms=duration_ms, breaker_state=permit_state, metadata={'exception_type': exc.__class__.__name__}))
                    last_exception = exc
                    last_non_ok_result = None
                    self._record_observability(tenant_id=tenant_id, entry=entry, operation=operation, phase=phase, status=classification.reason, trace_id=trace_id, duration_ms=duration_ms, fallback_depth=route_index, payload={'attempt': attempt_no, 'exception_type': exc.__class__.__name__, 'route_index': route_index, 'breaker_state': permit_state})
                    if classification.retryable and attempt_no < max_attempts:
                        self._sleep_retry(classification)
                        attempt_no += 1
                        continue
                    self._record_failure(entry=entry, operation=operation, reason=classification.reason, metadata={'exception_type': exc.__class__.__name__})
                    break

                duration_ms = (monotonic() - started) * 1000.0
                classification = self._retry_policy.classify_result(context=retry_context, result=result, attempt=attempt_no)
                attempts.append(self._attempt_row(entry=entry, operation=operation, route_index=route_index, attempt=attempt_no, phase=phase, outcome='success' if result.ok else 'result_error', reason=classification.reason, duration_ms=duration_ms, breaker_state=permit_state, metadata={'result_code': result.code}))
                self._record_observability(tenant_id=tenant_id, entry=entry, operation=operation, phase=phase, status='ok' if result.ok else 'result_error', trace_id=trace_id, duration_ms=duration_ms, fallback_depth=route_index, payload={'attempt': attempt_no, 'result_code': result.code, 'route_index': route_index, 'breaker_state': permit_state})
                if result.ok:
                    self._record_success(entry=entry, operation=operation)
                    return ConnectorFailoverResult(result=result, connector_id=entry.connector_id, provider=entry.provider, version=entry.version, operation=operation, fallback_depth=route_index, attempts=tuple(attempts))
                last_non_ok_result = (result, entry, route_index)
                last_exception = None
                if classification.retryable and attempt_no < max_attempts:
                    self._sleep_retry(classification)
                    attempt_no += 1
                    continue
                self._record_failure(entry=entry, operation=operation, reason=self._result_reason(result), metadata={'result_code': result.code})
                if self._should_failover_on_result(result=result, failover_on_result_codes=failover_on_result_codes, retry_context=retry_context):
                    break
                return ConnectorFailoverResult(result=result, connector_id=entry.connector_id, provider=entry.provider, version=entry.version, operation=operation, fallback_depth=route_index, attempts=tuple(attempts))
        if last_non_ok_result is not None:
            result, entry, route_index = last_non_ok_result
            return ConnectorFailoverResult(result=result, connector_id=entry.connector_id, provider=entry.provider, version=entry.version, operation=operation, fallback_depth=route_index, attempts=tuple(attempts))
        if last_exception is not None:
            raise last_exception
        raise RuntimeError(f'no healthy connector route for connector_id={connector_id} operation={operation}')

    def _route_safe_for_request(self, *, entry: ConnectorRegistryEntry, route_index: int, requested_version: str | None, retry_context: RetryContext, prior_call_attempted: bool) -> bool:
        if route_index == 0 or not retry_context.write or retry_context.dry_run or retry_context.idempotency_key_present:
            return True
        if prior_call_attempted:
            return False
        if requested_version is None:
            return True
        return str(entry.version) == str(requested_version).strip()

    def _record_success(self, *, entry: ConnectorRegistryEntry, operation: str) -> None:
        if self._circuit_breaker is not None:
            try:
                self._circuit_breaker.record_success(connector_id=entry.connector_id, provider=entry.provider, version=entry.version, operation=operation)
            except Exception:
                _LOG.warning('connector breaker success recording failed', exc_info=True, extra={'connector_id': entry.connector_id, 'provider': entry.provider, 'operation': operation})
        if self._health_monitor is not None:
            try:
                self._health_monitor.record(ConnectorHealthSample(connector_id=entry.connector_id, provider=entry.provider, version=entry.version, healthy=True, reason='runtime_success', metadata={'operation': operation}))
            except Exception:
                _LOG.warning('connector health success recording failed', exc_info=True, extra={'connector_id': entry.connector_id, 'provider': entry.provider, 'operation': operation})

    def _record_failure(self, *, entry: ConnectorRegistryEntry, operation: str, reason: str, metadata: Mapping[str, object] | None = None) -> None:
        if self._circuit_breaker is not None:
            try:
                self._circuit_breaker.record_failure(connector_id=entry.connector_id, provider=entry.provider, version=entry.version, operation=operation, reason=reason, metadata=metadata)
            except Exception:
                _LOG.warning('connector breaker failure recording failed', exc_info=True, extra={'connector_id': entry.connector_id, 'provider': entry.provider, 'operation': operation, 'reason': reason})
        if self._health_monitor is not None:
            try:
                self._health_monitor.record(ConnectorHealthSample(connector_id=entry.connector_id, provider=entry.provider, version=entry.version, healthy=False, reason=reason, metadata=dict(metadata or {}) | {'operation': operation}))
            except Exception:
                _LOG.warning('connector health failure recording failed', exc_info=True, extra={'connector_id': entry.connector_id, 'provider': entry.provider, 'operation': operation, 'reason': reason})

    def _record_observability(self, *, tenant_id: str, entry: ConnectorRegistryEntry, operation: str, phase: str, status: str, trace_id: str | None, duration_ms: float, fallback_depth: int, payload: Mapping[str, object]) -> None:
        if self._observability is None:
            return
        try:
            self._observability.record(ConnectorExecutionEvent(tenant_id=tenant_id, connector_id=entry.connector_id, provider=entry.provider, version=entry.version, operation=f'{phase}:{operation}', status=status, trace_id=trace_id, duration_ms=duration_ms, fallback_depth=fallback_depth, route_index=int(payload.get('route_index', fallback_depth)), attempt=int(payload.get('attempt', 0)), breaker_state=payload.get('breaker_state'), payload=dict(payload)))
        except Exception:
            _LOG.warning('connector observability recording failed', exc_info=True, extra={'tenant_id': tenant_id, 'connector_id': entry.connector_id, 'provider': entry.provider, 'operation': operation})

    def _sleep_retry(self, classification: RetryClassification) -> None:
        try:
            self._sleep(classification)
        except Exception:
            _LOG.warning('connector retry sleep failed', exc_info=True, extra={'attempt': classification.attempt, 'reason': classification.reason})

    def _attempt_row(self, *, entry: ConnectorRegistryEntry, operation: str, route_index: int, attempt: int, phase: str, outcome: str, reason: str, duration_ms: float, breaker_state: str | None, metadata: Mapping[str, object]) -> ConnectorRouteAttempt:
        return ConnectorRouteAttempt(connector_id=entry.connector_id, provider=entry.provider, version=entry.version, operation=f'{phase}:{operation}', route_index=int(route_index), attempt=int(attempt), phase=phase, outcome=outcome, reason=str(reason or ''), duration_ms=float(duration_ms), breaker_state=breaker_state, metadata=dict(metadata))

    def _result_reason(self, result: ConnectorResult) -> str:
        return str(getattr(result, 'code', '') or '').strip() or 'result_error'

    def _should_failover_on_result(self, *, result: ConnectorResult, failover_on_result_codes: tuple[str, ...], retry_context: RetryContext) -> bool:
        code = str(getattr(result, 'code', '') or '').strip().lower()
        if code not in {str(x).strip().lower() for x in failover_on_result_codes}:
            return False
        return not retry_context.write or retry_context.dry_run or retry_context.idempotency_key_present


__all__ = ['CANON_CONNECTOR_FAILOVER_ROUTER', 'ConnectorFailoverResult', 'ConnectorFailoverRouter', 'ConnectorRouteAttempt']
