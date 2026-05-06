from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True

from pathlib import Path

from bootstrap.assembly_runtime import build_event_log_and_bindings, resolve_tenant_and_pricing, validate_payments_webhook_prod_strict
from bootstrap.boot_observability import emit_boot_completed
from bootstrap.boot_phases import (
    boot_phase_30_durable_stores,
    boot_phase_40_load_settings_and_flags,
    boot_phase_50_telegram_outbound_queue,
    boot_phase_60_retention_adapter,
    boot_phase_70_policy_registry,
)
from bootstrap.security_boot_surface import build_security_boot_surface
from runtime.boot.boot_context import BootPhase
from runtime.boot.settings.messaging_settings_gateway import build_messaging_settings_gateway
from runtime.boot.system_builder_parts.runtime_services_finance import build_finance_bundle
from runtime.boot.system_builder_parts.runtime_services_result_builder import build_runtime_services_result
from runtime.boot.system_builder_parts.runtime_services_tenant import build_tenant_runtime_services
from runtime.boot.system_builder_steps import build_marketing_llm_components, wire_ads_stack_safely
from runtime.messaging_policy_events.event_store_adapter import EventLogMessagingPolicyEventStore
from runtime.messaging_policy_readmodel.boot_runtime import boot_messaging_policy_readmodel


def build_runtime_services(*, ctx, stack, base, storage, repo_root, model_registry_ctx):
    ctx.enter(BootPhase.P30_STORES)
    event_store, ledger, snapshot_store, decision_archive, outbox, payment_outbox = boot_phase_30_durable_stores(stack, base=base, storage=storage)
    durable_services = {
        'event_store': event_store,
        'ledger': ledger,
        'snapshot_store': snapshot_store,
        'decision_archive': decision_archive,
        'outbox': outbox,
        'payment_outbox': payment_outbox,
    }
    for key, value in durable_services.items():
        ctx.set_value(key, value, min_phase=BootPhase.P30_STORES)

    from runtime.governance import assert_governance_event_store_contract
    from runtime.wiring import build_behavior_graph_store

    assert_governance_event_store_contract(event_store)
    behavior_graph_store = build_behavior_graph_store(stack, base_dir=base, storage=storage)
    ctx.set_value('behavior_graph_store', behavior_graph_store, min_phase=BootPhase.P30_STORES)

    event_log, archive = build_event_log_and_bindings(event_store=event_store, decision_archive=decision_archive)
    settings_gateway = build_messaging_settings_gateway(event_store=event_store)
    messaging_policy_event_store = EventLogMessagingPolicyEventStore(event_log=event_log)
    messaging_policy_read_services = boot_messaging_policy_readmodel(runtime_obj=ctx, event_store=messaging_policy_event_store)
    messaging_services = {
        'event_log': event_log,
        'archive': archive,
        'settings_gateway': settings_gateway,
        'messaging_policy_event_store': messaging_policy_event_store,
        'messaging_policy_read_service': messaging_policy_read_services['read_service'],
    }
    for key, value in messaging_services.items():
        ctx.set_value(key, value, min_phase=BootPhase.P30_STORES)

    ctx.enter(BootPhase.P40_SETTINGS_FLAGS)
    settings, FeatureFlags, logging_mod = boot_phase_40_load_settings_and_flags()
    llm_components = build_marketing_llm_components(settings=settings, event_store=event_store, event_log=event_log, logging_mod=logging_mod)
    composer = llm_components['marketing_llm_composer']
    settings_services = {'settings': settings, 'FeatureFlags': FeatureFlags, 'composer': composer}
    ctx.set_value('marketing_llm_composer', composer, min_phase=BootPhase.P40_SETTINGS_FLAGS)
    ctx.set_value('marketing_llm', llm_components['marketing_llm'], min_phase=BootPhase.P40_SETTINGS_FLAGS)
    from runtime.boot.builders.ai_ceo_planner import build_runtime_ai_ceo_planner
    ctx.set_value('ai_ceo_planner', build_runtime_ai_ceo_planner(event_store=event_store), min_phase=BootPhase.P40_SETTINGS_FLAGS)
    validate_payments_webhook_prod_strict(settings)
    for key, value in settings_services.items():
        ctx.set_value(key, value, min_phase=BootPhase.P40_SETTINGS_FLAGS)

    ctx.enter(BootPhase.P50_OUTBOUND)
    telegram_outbound_queue = boot_phase_50_telegram_outbound_queue(settings=settings, event_log=event_log, logging_mod=logging_mod)
    pricing, tenant_id = resolve_tenant_and_pricing(settings)
    outbound_services = {'telegram_outbound_queue': telegram_outbound_queue, 'pricing': pricing, 'tenant_id': tenant_id}
    for key, value in outbound_services.items():
        ctx.set_value(key, value, min_phase=BootPhase.P50_OUTBOUND)

    tenant_runtime_services = build_tenant_runtime_services(tenant_id=tenant_id)
    for key, value in tenant_runtime_services.items():
        ctx.set_value(key, value, min_phase=BootPhase.P50_OUTBOUND)

    ctx.enter(BootPhase.P60_RETENTION)
    retention = boot_phase_60_retention_adapter(FeatureFlags=FeatureFlags, event_store=event_store, tenant_id=tenant_id, telegram_outbound_queue=telegram_outbound_queue, base=base, stack=stack)
    ctx.set_value('retention', retention, min_phase=BootPhase.P60_RETENTION)
    ads_components = wire_ads_stack_safely(tenant_id=tenant_id, repo_root=repo_root, event_store=event_store, event_log=event_log, logging_mod=logging_mod, composer=composer)
    for key, value in ads_components.items():
        ctx.set_value(key, value, min_phase=BootPhase.P60_RETENTION)

    ctx.enter(BootPhase.P70_POLICIES)
    preg = boot_phase_70_policy_registry(settings=settings, pricing=pricing, retention=retention, logging_mod=logging_mod)
    ctx.set_value('policy_registry', preg, min_phase=BootPhase.P70_POLICIES)
    policy_services = {'preg': preg}

    security_surface = build_security_boot_surface(audit_path=Path(base) / 'security' / 'process_owner_security_audit.jsonl')
    ctx.set_value('api_security_owner_bundle', security_surface.api_security_owner_bundle, min_phase=BootPhase.P70_POLICIES)
    security_services = {'api_security_owner_bundle': security_surface.api_security_owner_bundle}

    finance_bundle = build_finance_bundle(event_log=event_log)
    for key in ('finance_runtime', 'finance_job_registry', 'finance_event_registry', 'finance_job_specs', 'finance_job_orchestrator'):
        ctx.set_value(key, finance_bundle[key], min_phase=BootPhase.P70_POLICIES)
    finance_host_binding = finance_bundle['finance_host_binding']
    ctx.set_value('host_job_catalog', finance_host_binding.job_catalog, min_phase=BootPhase.P70_POLICIES)
    ctx.set_value('finance_event_read_model', finance_host_binding.event_read_model, min_phase=BootPhase.P70_POLICIES)
    ctx.set_value('finance_observability', finance_host_binding.observability_sink, min_phase=BootPhase.P70_POLICIES)

    emit_boot_completed(
        event_store=event_store,
        tenant_id=tenant_id,
        run_mode=str(ctx.get_value('run_mode')),
        env=str(ctx.get_value('env')),
        components={
            'event_store': event_store is not None,
            'decision_core': True,
            'telegram_outbound_queue': telegram_outbound_queue is not None,
            'ads_runtime': ctx.get_value('ads_runtime') is not None,
            'marketing_llm': ctx.get_value('marketing_llm') is not None,
            'finance_runtime': finance_bundle['finance_runtime'] is not None,
            'api_security_owner_bundle': security_surface.api_security_owner_bundle is not None,
        },
    )

    return build_runtime_services_result(
        tenant_runtime_services=tenant_runtime_services,
        finance_bundle=finance_bundle,
        model_registry_ctx=model_registry_ctx,
        durable_services=durable_services,
        messaging_services=messaging_services,
        settings_services=settings_services,
        outbound_services=outbound_services,
        policy_services=policy_services,
        security_services=security_services,
    )
