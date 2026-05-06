from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Callable, Mapping

from execution.market_intelligence_business_memory_bridge import MarketIntelligenceBusinessMemoryBridge
from execution.market_intelligence_circuit_breaker import MarketIntelligenceCircuitBreaker
from execution.market_intelligence_compliance_boundary import MarketIntelligenceComplianceBoundary
from execution.market_intelligence_dataset_builder import MarketIntelligenceDatasetBuilder
from execution.market_intelligence_dedup import MarketIntelligenceDeduplicator
from execution.market_intelligence_economic_control import MarketIntelligenceEconomicControl
from execution.market_intelligence_evaluation import MarketIntelligenceEvaluationFramework
from execution.market_intelligence_governance import MarketIntelligenceGovernance
from execution.market_intelligence_idempotency import MarketIntelligenceIdempotencyStore, build_market_intelligence_idempotency_key
from execution.market_intelligence_models import MarketIntelligenceIngestionRequest
from execution.market_intelligence_normalizer import MarketIntelligenceRecordNormalizer
from execution.market_intelligence_observability import MarketIntelligenceTelemetry
from execution.market_intelligence_observability_store import MarketIntelligenceRunSummary, PersistentMarketIntelligenceObservabilityStore
from execution.market_intelligence_operator_control_plane import MarketIntelligenceOperatorControlPlane
from execution.market_intelligence_policy import MarketIntelligencePolicy
from execution.market_intelligence_quota_guard import MarketIntelligenceQuotaGuard
from execution.market_intelligence_retry_policy import MarketIntelligenceRetryPolicy
from execution.market_intelligence_tenancy_scope import MarketIntelligenceTenancyScope
from execution.market_intelligence_world_state_adapter import MarketIntelligenceWorldStateAdapter


CANON_MARKET_INTELLIGENCE_LOOP = True


class MarketIntelligenceExecutionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = str(code or 'provider_error')


@dataclass
class MarketIntelligenceLoop:
    execute_action: Callable[[str, Mapping[str, Any]], Mapping[str, Any]]
    policy: MarketIntelligencePolicy = field(default_factory=MarketIntelligencePolicy)
    governance: MarketIntelligenceGovernance = field(default_factory=MarketIntelligenceGovernance)
    compliance: MarketIntelligenceComplianceBoundary = field(default_factory=MarketIntelligenceComplianceBoundary)
    economic_control: MarketIntelligenceEconomicControl = field(default_factory=MarketIntelligenceEconomicControl)
    operator_control: MarketIntelligenceOperatorControlPlane = field(default_factory=MarketIntelligenceOperatorControlPlane)
    quota_guard: MarketIntelligenceQuotaGuard = field(default_factory=MarketIntelligenceQuotaGuard)
    retry_policy: MarketIntelligenceRetryPolicy = field(default_factory=MarketIntelligenceRetryPolicy)
    circuit_breaker: MarketIntelligenceCircuitBreaker = field(default_factory=MarketIntelligenceCircuitBreaker)
    idempotency_store: MarketIntelligenceIdempotencyStore = field(default_factory=MarketIntelligenceIdempotencyStore)
    normalizer: MarketIntelligenceRecordNormalizer = field(default_factory=MarketIntelligenceRecordNormalizer)
    deduplicator: MarketIntelligenceDeduplicator = field(default_factory=MarketIntelligenceDeduplicator)
    dataset_builder: MarketIntelligenceDatasetBuilder = field(default_factory=MarketIntelligenceDatasetBuilder)
    world_state_adapter: MarketIntelligenceWorldStateAdapter = field(default_factory=MarketIntelligenceWorldStateAdapter)
    memory_bridge: MarketIntelligenceBusinessMemoryBridge = field(default_factory=MarketIntelligenceBusinessMemoryBridge)
    telemetry: MarketIntelligenceTelemetry = field(default_factory=MarketIntelligenceTelemetry)
    observability_store: PersistentMarketIntelligenceObservabilityStore = field(default_factory=PersistentMarketIntelligenceObservabilityStore)
    evaluation: MarketIntelligenceEvaluationFramework = field(default_factory=MarketIntelligenceEvaluationFramework)
    operator_low_quality_threshold: float = 0.34

    def run(self, request: MarketIntelligenceIngestionRequest, *, tenancy_scope: MarketIntelligenceTenancyScope | None = None) -> dict[str, Any]:
        validated = self.policy.validate_request(request)
        scoped, risk = self.governance.enforce(validated, tenancy_scope=tenancy_scope)
        idempotency_key = build_market_intelligence_idempotency_key(scoped)
        cached = self.idempotency_store.get(idempotency_key)
        if cached is not None:
            cached_result = dict(cached)
            cached_result['idempotency_hit'] = True
            cached_result['telemetry_snapshot'] = self.telemetry.snapshot()
            cached_result['quota_snapshot'] = self.quota_guard.snapshot()
            cached_result['circuit_breaker_snapshot'] = self.circuit_breaker.snapshot()
            cached_result['operator_snapshot'] = self.operator_control.snapshot()
            self.telemetry.emit('market_intelligence_idempotency_hit', provider=scoped.provider, tenant_id=scoped.tenant_id)
            return cached_result

        self.quota_guard.consume(scoped)
        self.economic_control.ensure_allowed(tenant_id=scoped.tenant_id, provider=scoped.provider, estimated_cost=0.0)
        self.circuit_breaker.ensure_open(scoped.provider)

        payload = scoped.as_payload()
        payload['provider'] = scoped.provider
        payload['source_family'] = scoped.source_family
        payload['tenant_id'] = scoped.tenant_id
        payload['risk'] = risk
        payload['idempotency_key'] = idempotency_key
        payload = self.compliance.enforce_pre_ingestion(provider=scoped.provider, payload=payload)
        scope_key = self._scope_key(payload)
        self.operator_control.check_source_allowed(tenant_id=scoped.tenant_id, provider=scoped.provider, scope_key=scope_key)

        trace_id = f'mi-trace:{idempotency_key[:16]}'
        self.telemetry.start_trace(trace_id=trace_id, run_id=idempotency_key[:16], tenant_id=scoped.tenant_id, provider=scoped.provider, source_family=scoped.source_family, operation=scoped.action_type)
        attempt = 1
        started = time.monotonic()

        while True:
            try:
                raw_result = self.execute_action(scoped.action_type, payload) or {}
                result = self._normalize_result_payload(raw_result)
                if not bool(result.get('ok', True)):
                    raise MarketIntelligenceExecutionError(str(result.get('code') or 'provider_error'), str(result.get('message') or 'provider returned not-ok result'))
                if result.get('executed') is False:
                    raise MarketIntelligenceExecutionError(str(result.get('code') or 'provider_error'), str(result.get('message') or 'action did not execute'))

                result.setdefault('provider', scoped.provider)
                result.setdefault('source_family', scoped.source_family)
                result.setdefault('action_type', scoped.action_type)
                result.setdefault('tenant_id', scoped.tenant_id)

                pre_dedup = [self.normalizer.normalize_record(item) for item in list(result.get('records') or []) if isinstance(item, Mapping)]
                normalized_records = self.deduplicator.deduplicate(pre_dedup)
                result['records'] = normalized_records
                result['policy_summary'] = self.policy.summarize_result(result)
                result['summary'] = dict(result['policy_summary'])
                result['dataset_rows'] = [row.as_dict() for row in self.dataset_builder.build_rows(result)]

                memory_payload = self.memory_bridge.to_memory_payload(result)
                result['memory_payload'] = memory_payload
                if memory_payload.get('derived_evidence'):
                    result['derived_evidence'] = memory_payload.get('derived_evidence')
                    self.telemetry.emit_provenance_audit(
                        tenant_id=scoped.tenant_id,
                        evidence_id=str(memory_payload['derived_evidence'].get('evidence_id') or ''),
                        source_provider=scoped.provider,
                        source_family=scoped.source_family,
                        derived_kind=str(memory_payload['derived_evidence'].get('derived_kind') or 'market_signal_summary'),
                        policy_name=str(memory_payload['derived_evidence'].get('policy_name') or 'market_intelligence_derived_evidence_v1'),
                    )
                    self.observability_store.append_provenance(
                        tenant_id=scoped.tenant_id,
                        evidence_id=str(memory_payload['derived_evidence'].get('evidence_id') or ''),
                        provider=scoped.provider,
                        source_family=scoped.source_family,
                        derived_kind=str(memory_payload['derived_evidence'].get('derived_kind') or 'market_signal_summary'),
                        policy_name=str(memory_payload['derived_evidence'].get('policy_name') or 'market_intelligence_derived_evidence_v1'),
                    )

                result['world_state_patch'] = self.world_state_adapter.to_world_state_patch(result)
                quality_score = self.evaluation.provider_quality_score(records=normalized_records)
                result['risk'] = risk
                result['governance'] = {
                    'risk_level': risk.get('risk_level'),
                    'requires_approval': bool(risk.get('requires_approval')),
                    'provider_validated': True,
                    'compliance': dict(payload.get('compliance') or {}),
                }
                result['idempotency_key'] = idempotency_key
                result['idempotency_hit'] = False
                result['evaluation'] = self.evaluation.regression_summary(provider_records=normalized_records, fused_entities=[], golden=[])
                result['evaluation']['provider_quality_score'] = quality_score

                self.idempotency_store.put(idempotency_key, result)
                self.economic_control.record_usage(tenant_id=scoped.tenant_id, provider=scoped.provider, cost=0.0)
                self.circuit_breaker.on_success(scoped.provider)

                latency_ms = (time.monotonic() - started) * 1000.0
                self.telemetry.observe_latency(provider=scoped.provider, source_family=scoped.source_family, latency_ms=latency_ms)
                self.telemetry.observe_dedup_effectiveness(provider=scoped.provider, before_count=len(pre_dedup), after_count=len(normalized_records))
                self.telemetry.observe_source_quality(provider=scoped.provider, score=quality_score)
                self.telemetry.emit('market_intelligence_sync_succeeded', provider=scoped.provider, tenant_id=scoped.tenant_id, records=len(normalized_records), action_type=scoped.action_type)
                self.telemetry.finish_trace(trace_id=trace_id, status='succeeded', records=len(normalized_records), quality_score=quality_score)

                self.observability_store.append_run(MarketIntelligenceRunSummary(
                    run_id=idempotency_key[:16],
                    tenant_id=scoped.tenant_id,
                    provider=scoped.provider,
                    source_family=scoped.source_family,
                    action_type=scoped.action_type,
                    status='succeeded',
                    records_count=len(normalized_records),
                    quality_score=quality_score,
                    metadata={'scope_key': scope_key},
                ))

                if not normalized_records:
                    review_id = self.operator_control.enqueue_review(
                        tenant_id=scoped.tenant_id,
                        provider=scoped.provider,
                        source_family=scoped.source_family,
                        external_id='none',
                        reason='empty_result',
                        payload={'action_type': scoped.action_type, 'scope_key': scope_key, 'query': scoped.query, 'subject_url': scoped.subject_url},
                    )
                    self.operator_control.escalate_review(review_id=review_id, operator_id=None, reason='empty_result')
                    self.observability_store.append_anomaly(tenant_id=scoped.tenant_id, provider=scoped.provider, source_family=scoped.source_family, reason='empty_result', payload={'review_id': review_id, 'scope_key': scope_key})
                elif quality_score < float(self.operator_low_quality_threshold):
                    review_id = self.operator_control.enqueue_review(
                        tenant_id=scoped.tenant_id,
                        provider=scoped.provider,
                        source_family=scoped.source_family,
                        external_id=str(normalized_records[0].get('external_id') or 'unknown'),
                        reason='low_quality_result',
                        payload={'action_type': scoped.action_type, 'scope_key': scope_key, 'provider_quality_score': quality_score},
                    )
                    self.observability_store.append_anomaly(tenant_id=scoped.tenant_id, provider=scoped.provider, source_family=scoped.source_family, reason='low_quality_result', payload={'review_id': review_id, 'provider_quality_score': quality_score})

                result['telemetry_snapshot'] = self.telemetry.snapshot()
                result['observability_snapshot'] = self.observability_store.snapshot()
                result['quota_snapshot'] = self.quota_guard.snapshot()
                result['circuit_breaker_snapshot'] = self.circuit_breaker.snapshot()
                result['operator_snapshot'] = self.operator_control.snapshot()
                return result
            except MarketIntelligenceExecutionError as exc:
                if self.retry_policy.should_retry(code=exc.code, attempt=attempt):
                    self.telemetry.emit('market_intelligence_retry_scheduled', provider=scoped.provider, tenant_id=scoped.tenant_id, attempt=attempt, code=exc.code)
                    time.sleep(self.retry_policy.backoff_seconds(attempt))
                    attempt += 1
                    continue
                self.circuit_breaker.on_failure(scoped.provider)
                self.telemetry.observe_error(provider=scoped.provider, code=exc.code)
                self.telemetry.emit('market_intelligence_sync_failed', provider=scoped.provider, tenant_id=scoped.tenant_id, attempt=attempt, code=exc.code)
                self.telemetry.finish_trace(trace_id=trace_id, status='failed', error_code=exc.code)
                review_id = self.operator_control.enqueue_review(
                    tenant_id=scoped.tenant_id,
                    provider=scoped.provider,
                    source_family=scoped.source_family,
                    external_id='none',
                    reason='execution_failed',
                    payload={'action_type': scoped.action_type, 'scope_key': scope_key, 'code': exc.code, 'message': str(exc)},
                )
                self.operator_control.escalate_review(review_id=review_id, operator_id=None, reason=exc.code)
                self.observability_store.append_anomaly(tenant_id=scoped.tenant_id, provider=scoped.provider, source_family=scoped.source_family, reason='execution_failed', payload={'review_id': review_id, 'code': exc.code})
                self.observability_store.append_run(MarketIntelligenceRunSummary(
                    run_id=idempotency_key[:16], tenant_id=scoped.tenant_id, provider=scoped.provider, source_family=scoped.source_family, action_type=scoped.action_type, status='failed', metadata={'scope_key': scope_key, 'code': exc.code}
                ))
                raise
            except Exception as exc:
                wrapped = MarketIntelligenceExecutionError('provider_error', str(exc) or exc.__class__.__name__)
                if self.retry_policy.should_retry(code=wrapped.code, attempt=attempt):
                    self.telemetry.emit('market_intelligence_retry_scheduled', provider=scoped.provider, tenant_id=scoped.tenant_id, attempt=attempt, code=wrapped.code)
                    time.sleep(self.retry_policy.backoff_seconds(attempt))
                    attempt += 1
                    continue
                self.circuit_breaker.on_failure(scoped.provider)
                self.telemetry.observe_error(provider=scoped.provider, code=wrapped.code)
                self.telemetry.emit('market_intelligence_sync_failed', provider=scoped.provider, tenant_id=scoped.tenant_id, attempt=attempt, code=wrapped.code)
                self.telemetry.finish_trace(trace_id=trace_id, status='failed', error_code=wrapped.code)
                review_id = self.operator_control.enqueue_review(
                    tenant_id=scoped.tenant_id,
                    provider=scoped.provider,
                    source_family=scoped.source_family,
                    external_id='none',
                    reason='execution_failed',
                    payload={'action_type': scoped.action_type, 'scope_key': scope_key, 'code': wrapped.code, 'message': str(wrapped)},
                )
                self.operator_control.escalate_review(review_id=review_id, operator_id=None, reason=wrapped.code)
                self.observability_store.append_anomaly(tenant_id=scoped.tenant_id, provider=scoped.provider, source_family=scoped.source_family, reason='execution_failed', payload={'review_id': review_id, 'code': wrapped.code})
                self.observability_store.append_run(MarketIntelligenceRunSummary(
                    run_id=idempotency_key[:16], tenant_id=scoped.tenant_id, provider=scoped.provider, source_family=scoped.source_family, action_type=scoped.action_type, status='failed', metadata={'scope_key': scope_key, 'code': wrapped.code}
                ))
                raise wrapped

    @staticmethod
    def _normalize_result_payload(raw_result: Mapping[str, Any]) -> dict[str, Any]:
        result = dict(raw_result or {})
        records = result.get('records')
        if not isinstance(records, list):
            result['records'] = []
        return result

    @staticmethod
    def _scope_key(payload: Mapping[str, Any]) -> str:
        for key in ('subject_url', 'query', 'account_ref'):
            value = str(payload.get(key) or '').strip()
            if value:
                return value
        return 'global'
