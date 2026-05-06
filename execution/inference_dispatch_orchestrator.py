from __future__ import annotations

from execution.inference_capacity_policy import InferenceCapacityPolicyContext
from execution.inference_capacity_router import InferenceCapacityRouter
from execution.inference_capacity_contract import InferenceCapacityTier
from execution.inference_cold_start_policy import InferenceColdStartPolicy
from execution.inference_degradation_playbook import InferenceDegradationPlaybook
from execution.inference_fairness_scheduler import InferenceFairnessScheduler
from execution.inference_policy_guard import InferencePolicyEnvelope, InferencePolicyGuard
from execution.inference_execution_result_contract import InferenceExecutionRecord
from execution.inference_fallback_chain import InferenceFallbackChain
from execution.inference_provider_contract import InferenceProvider, InferenceRequest
from execution.inference_result_verifier import InferenceResultVerifier
from execution.inference_workload_classifier import InferenceWorkloadClassifier
from runtime.inference.providers.provider_circuit_breaker import ProviderCircuitBreaker
from runtime.inference.providers.provider_rate_limit_guard import ProviderRateLimitGuard
from runtime.inference.providers.provider_retry_adapter import ProviderRetryAdapter
from runtime.inference.providers.provider_acceleration_profile import InferenceProviderAccelerationProfileCatalog
from runtime.inference.providers.provider_batch_execution_policy import ProviderBatchExecutionPolicy
from runtime.inference.providers.provider_memory_transfer_policy import ProviderMemoryTransferPolicy
from runtime.inference.providers.provider_acceleration_pressure_policy import ProviderAccelerationPressurePolicy
from observability.inference_acceleration_log import InferenceAccelerationLog


CANON_INFERENCE_DISPATCH_ORCHESTRATOR = True


class InferenceDispatchOrchestrator:
    _replay_cache: dict[str, InferenceExecutionRecord]

    @staticmethod
    def _safe_float(value: object, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_int(value: object, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def __init__(
        self,
        *,
        providers: dict[str, InferenceProvider],
        router: InferenceCapacityRouter,
        classifier: InferenceWorkloadClassifier | None = None,
        verifier: InferenceResultVerifier | None = None,
        policy_guard: InferencePolicyGuard | None = None,
        cold_start_policy: InferenceColdStartPolicy | None = None,
        degradation_playbook: InferenceDegradationPlaybook | None = None,
        fairness_scheduler: InferenceFairnessScheduler | None = None,
        fallback_chain: InferenceFallbackChain | None = None,
        retry_adapter: ProviderRetryAdapter | None = None,
        circuit_breaker: ProviderCircuitBreaker | None = None,
        rate_limit_guard: ProviderRateLimitGuard | None = None,
        acceleration_catalog: InferenceProviderAccelerationProfileCatalog | None = None,
        batch_policy: ProviderBatchExecutionPolicy | None = None,
        memory_transfer_policy: ProviderMemoryTransferPolicy | None = None,
        acceleration_log: InferenceAccelerationLog | None = None,
        acceleration_pressure_policy: ProviderAccelerationPressurePolicy | None = None,
    ) -> None:
        self._providers = dict(providers)
        self._router = router
        self._classifier = classifier or InferenceWorkloadClassifier()
        self._verifier = verifier or InferenceResultVerifier()
        self._policy_guard = policy_guard or InferencePolicyGuard()
        self._cold_start_policy = cold_start_policy or InferenceColdStartPolicy()
        self._degradation_playbook = degradation_playbook or InferenceDegradationPlaybook()
        self._fairness_scheduler = fairness_scheduler or InferenceFairnessScheduler()
        self._fallback_chain = fallback_chain or InferenceFallbackChain()
        self._retry_adapter = retry_adapter or ProviderRetryAdapter()
        self._circuit_breaker = circuit_breaker or ProviderCircuitBreaker()
        self._rate_limit_guard = rate_limit_guard or ProviderRateLimitGuard()
        self._acceleration_catalog = acceleration_catalog or InferenceProviderAccelerationProfileCatalog()
        self._batch_policy = batch_policy or ProviderBatchExecutionPolicy()
        self._memory_transfer_policy = memory_transfer_policy or ProviderMemoryTransferPolicy(
            catalog=self._acceleration_catalog
        )
        self._acceleration_log = acceleration_log or InferenceAccelerationLog()
        self._acceleration_pressure_policy = acceleration_pressure_policy or ProviderAccelerationPressurePolicy()
        self._replay_cache = {}

    def dispatch(
        self,
        *,
        request: InferenceRequest,
        preferred_tier: InferenceCapacityTier,
        policy_context: InferenceCapacityPolicyContext,
    ) -> InferenceExecutionRecord:
        metadata = dict(request.metadata)
        replay_mode = str(metadata.get('replay_safe_dispatch', 'true')).strip().lower() in {'1', 'true', 'yes', 'on'}
        if replay_mode and request.request_id in self._replay_cache:
            return self._replay_cache[request.request_id]
        workload = self._classifier.classify(prompt=request.prompt, metadata=metadata)
        historical_executions = self._safe_int(metadata.get('historical_inference_executions'))
        cold_start = self._cold_start_policy.evaluate(
            historical_executions=historical_executions,
            requested_tier=preferred_tier,
        )
        selection = self._router.select(
            workload=workload,
            preferred_tier=cold_start.preferred_tier,
            policy_context=policy_context,
        )
        policy_envelope = InferencePolicyEnvelope.from_payload(
            {
                **metadata,
                'tenant_id': policy_context.tenant_id,
                'inference_requested_tier': selection.tier.value,
                'inference_estimated_cost_usd': selection.estimated_cost_usd,
                'inference_distributed_enabled': policy_context.distributed_network_enabled,
                'inference_premium_enabled': policy_context.premium_cloud_enabled,
            }
        )
        policy_verdict = self._policy_guard.evaluate(policy_envelope)
        if not policy_verdict.allowed:
            raise RuntimeError(f"inference policy denied selection: {policy_verdict.reason}")
        budget_cap_usd = self._safe_float(metadata.get('inference_budget_cap_usd'), 25.0)
        degradation = self._degradation_playbook.evaluate(
            current_tier=selection.tier,
            budget_pressure=selection.estimated_cost_usd > budget_cap_usd,
            provider_failure=False,
        )
        if degradation.target_tier != selection.tier:
            selection = self._router.select(
                workload=workload,
                preferred_tier=degradation.target_tier,
                policy_context=policy_context,
            )
        provider = self._providers[selection.provider_name]
        fallback_reason = 'none'
        fallback_provider_name = ''
        attempted_providers: list[str] = []
        attempted_tiers: list[str] = []

        def _run_with_provider(active_provider):
            attempted_providers.append(active_provider.name)
            attempted_tiers.append(active_provider.profile.tier.value)
            if not self._circuit_breaker.allows(active_provider.name):
                raise RuntimeError(f"inference provider '{active_provider.name}' is temporarily blocked by circuit breaker")
            if not self._rate_limit_guard.allows(active_provider.name):
                raise RuntimeError(f"inference provider '{active_provider.name}' exceeded canonical rate limit")

            def _call_provider():
                self._rate_limit_guard.record(active_provider.name)
                return active_provider.infer(request)

            try:
                result = self._retry_adapter.run(_call_provider)
                self._circuit_breaker.record_success(active_provider.name)
                return result
            except Exception:
                self._circuit_breaker.record_failure(active_provider.name)
                raise

        response = None
        verification = None
        last_error: Exception | None = None
        fallback_trigger = 'none'

        candidate_tiers = (selection.tier,) + self._fallback_chain.failover_tiers(selection.tier)
        for index, candidate_tier in enumerate(candidate_tiers):
            try:
                active_selection = selection if index == 0 else self._router.select(
                    workload=workload,
                    preferred_tier=candidate_tier,
                    policy_context=policy_context,
                )
                active_provider = self._providers[active_selection.provider_name]
                active_response = _run_with_provider(active_provider)
                active_verification = self._verifier.verify(active_response)
                if active_verification.accepted:
                    response = active_response
                    verification = active_verification
                    selection = active_selection
                    provider = active_provider
                    if index > 0:
                        fallback_reason = f'{fallback_trigger}_failover' if fallback_trigger != 'none' else 'fallback'
                        fallback_provider_name = active_provider.name
                    break
                last_error = RuntimeError(f"verification rejected by provider '{active_provider.name}': {active_verification.reason}")
                fallback_trigger = 'verification'
                continue
            except Exception as exc:
                last_error = exc
                if fallback_trigger == 'none':
                    fallback_trigger = 'provider_failure'
                continue

        if response is None or verification is None:
            if last_error is not None:
                raise last_error
            raise RuntimeError('inference dispatch exhausted all fallback tiers without producing a verified response')

        acceleration_profile = self._acceleration_catalog.profile_for_tier(tier=selection.tier)
        provider_health = provider.health()
        batch_plan = self._batch_policy.plan(
            provider=provider,
            requested_batch_items=self._safe_int(metadata.get('requested_batch_items'), 1),
        )
        transfer_plan = self._memory_transfer_policy.plan(provider=provider)
        pressure_plan = self._acceleration_pressure_policy.plan(
            profile=acceleration_profile,
            transfer_plan=transfer_plan,
            health=provider_health,
        )

        fairness = self._fairness_scheduler.allocate([{'tenant_id': policy_context.tenant_id or 'global', 'queue_depth': self._safe_int(metadata.get('tenant_queue_depth'), 1)}])
        self._acceleration_log.record(
            tenant_id=policy_context.tenant_id or 'global',
            provider_name=provider.name,
            tier=selection.tier.value,
            execution_mode=acceleration_profile.execution_mode,
            device_class=acceleration_profile.device_class,
            transport_kind=transfer_plan.transport_kind,
            prefers_local_memory=acceleration_profile.prefers_local_memory,
            batch_items=batch_plan.batch_items,
            provider_max_batch_items=provider.profile.limits.max_batch_items,
            expected_transfer_overhead_ms=transfer_plan.expected_overhead_ms,
            saturation_score=pressure_plan.saturation_score,
            pressure_band=pressure_plan.pressure_band,
            locality_scope=pressure_plan.locality_scope,
            expected_queue_penalty_ms=pressure_plan.expected_queue_penalty_ms,
        )

        record = InferenceExecutionRecord(
            response=response,
            verification=verification,
            selected_provider=selection.provider_name,
            selected_tier=selection.tier.value,
            evidence={
                'selection_reason': selection.reason,
                'estimated_cost_usd': f'{selection.estimated_cost_usd:.6f}',
                'provider_name': provider.name,
                'policy_reason': policy_verdict.reason,
                'policy_requires_human_review': str(policy_verdict.requires_human_review).lower(),
                'cold_start_reason': cold_start.reason,
                'degradation_mode': degradation.mode,
                'degradation_reason': degradation.reason,
                'fairness_allocated_share': f"{fairness[0].allocated_share:.6f}" if fairness else '0.000000',
                'fallback_reason': fallback_reason,
                'fallback_provider_name': fallback_provider_name,
                'acceleration_execution_mode': acceleration_profile.execution_mode,
                'acceleration_device_class': acceleration_profile.device_class,
                'acceleration_transport_kind': transfer_plan.transport_kind,
                'acceleration_prefers_local_memory': str(acceleration_profile.prefers_local_memory).lower(),
                'acceleration_batch_items': str(batch_plan.batch_items),
                'acceleration_provider_max_batch_items': str(provider.profile.limits.max_batch_items),
                'acceleration_transfer_overhead_ms': str(transfer_plan.expected_overhead_ms),
                'acceleration_pressure_band': pressure_plan.pressure_band,
                'acceleration_locality_scope': pressure_plan.locality_scope,
                'acceleration_saturation_score': f"{pressure_plan.saturation_score:.6f}",
                'acceleration_expected_queue_penalty_ms': str(pressure_plan.expected_queue_penalty_ms),
                'attempted_providers': ','.join(attempted_providers),
                'attempted_tiers': ','.join(attempted_tiers),
                'recovery_attempt_count': str(len(attempted_providers)),
            },
        )
        if replay_mode:
            self._replay_cache[request.request_id] = record
        return record
