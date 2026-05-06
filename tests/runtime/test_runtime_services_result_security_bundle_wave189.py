from runtime.boot.system_builder_parts.runtime_services_result_builder import build_runtime_services_result
from runtime.runtime_infra import RuntimeInfra


def test_runtime_services_result_carries_api_security_owner_bundle_into_runtime_infra() -> None:
    shared_bundle = object()
    result = build_runtime_services_result(
        tenant_runtime_services={'tenant_registry': object(),'tenant_policy_store': object(),'tenant_quota_guard': object(),'tenant_runtime_isolation': object(),'tenant_execution_budget_guard': object(),'tenant_runtime_lease_store': object(),'tenant_admission_backend': object(),'tenant_runtime_reconciler': object(),'tenant_runtime_fencing_registry': object(),'tenant_metrics_store': object(),'tenant_migration_lock_backend': object()},
        finance_bundle={'finance_runtime': object(),'finance_job_registry': object(),'finance_event_registry': object(),'finance_job_specs': object(),'finance_job_orchestrator': object(),'finance_host_binding': type('FinanceHostBinding', (), {'job_catalog': object(), 'event_read_model': object(), 'observability_sink': object()})()},
        model_registry_ctx=object(),
        durable_services={'event_store': object(),'ledger': object(),'snapshot_store': object(),'decision_archive': object(),'outbox': object(),'payment_outbox': object()},
        messaging_services={'event_log': object(),'archive': object(),'settings_gateway': object(),'messaging_policy_event_store': object(),'messaging_policy_read_service': object()},
        settings_services={'settings': object(), 'FeatureFlags': object(), 'composer': object()},
        outbound_services={'telegram_outbound_queue': object(), 'pricing': object(), 'tenant_id': 'tenant-a'},
        policy_services={'preg': object()},
        security_services={'api_security_owner_bundle': shared_bundle},
    )
    assert isinstance(result.runtime_infra, RuntimeInfra)
    assert result.runtime_infra.api_security_owner_bundle is shared_bundle
