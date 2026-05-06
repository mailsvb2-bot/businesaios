from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True

from runtime.boot.system_builder_parts.runtime_services_result import RuntimeServicesResult


def build_runtime_services_result(*, tenant_runtime_services: dict[str, object], finance_bundle: dict[str, object], model_registry_ctx, durable_services: dict[str, object], messaging_services: dict[str, object], settings_services: dict[str, object], outbound_services: dict[str, object], policy_services: dict[str, object], security_services: dict[str, object] | None = None):
    finance_host_binding = finance_bundle['finance_host_binding']
    return RuntimeServicesResult(
        event_store=durable_services['event_store'],
        ledger=durable_services['ledger'],
        snapshot_store=durable_services['snapshot_store'],
        decision_archive=durable_services['decision_archive'],
        outbox=durable_services['outbox'],
        payment_outbox=durable_services['payment_outbox'],
        event_log=messaging_services['event_log'],
        archive=messaging_services['archive'],
        settings_gateway=messaging_services['settings_gateway'],
        messaging_policy_event_store=messaging_services['messaging_policy_event_store'],
        messaging_policy_read_service=messaging_services['messaging_policy_read_service'],
        tenant_registry=tenant_runtime_services['tenant_registry'],
        tenant_policy_store=tenant_runtime_services['tenant_policy_store'],
        tenant_quota_guard=tenant_runtime_services['tenant_quota_guard'],
        tenant_runtime_isolation=tenant_runtime_services['tenant_runtime_isolation'],
        tenant_execution_budget_guard=tenant_runtime_services['tenant_execution_budget_guard'],
        tenant_runtime_lease_store=tenant_runtime_services['tenant_runtime_lease_store'],
        tenant_admission_backend=tenant_runtime_services['tenant_admission_backend'],
        tenant_runtime_reconciler=tenant_runtime_services['tenant_runtime_reconciler'],
        tenant_runtime_fencing_registry=tenant_runtime_services['tenant_runtime_fencing_registry'],
        tenant_metrics_store=tenant_runtime_services['tenant_metrics_store'],
        tenant_migration_lock_backend=tenant_runtime_services['tenant_migration_lock_backend'],
        api_security_owner_bundle=(dict(security_services or {})).get('api_security_owner_bundle'),
        settings=settings_services['settings'],
        FeatureFlags=settings_services['FeatureFlags'],
        composer=settings_services['composer'],
        telegram_outbound_queue=outbound_services['telegram_outbound_queue'],
        pricing=outbound_services['pricing'],
        tenant_id=outbound_services['tenant_id'],
        preg=policy_services['preg'],
        policy_selector=None,
        model_registry=model_registry_ctx,
        finance_runtime=finance_bundle['finance_runtime'],
        finance_job_registry=finance_bundle['finance_job_registry'],
        finance_event_registry=finance_bundle['finance_event_registry'],
        finance_job_specs=finance_bundle['finance_job_specs'],
        finance_job_orchestrator=finance_bundle['finance_job_orchestrator'],
        host_job_catalog=finance_host_binding.job_catalog,
        finance_event_read_model=finance_host_binding.event_read_model,
        finance_observability=finance_host_binding.observability_sink,
    )
