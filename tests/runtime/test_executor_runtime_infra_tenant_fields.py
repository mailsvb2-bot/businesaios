from runtime.execution.executor_state import (
    RuntimeExecutorInfra,
    build_executor_runtime_infra_from_runtime_infra,
    build_runtime_infra,
)


def test_build_runtime_infra_preserves_tenant_fields():
    base = RuntimeExecutorInfra(tenant_registry=object(), tenant_policy_store=object(), tenant_quota_guard=object(), tenant_runtime_isolation=object(), tenant_execution_budget_guard=object(), tenant_runtime_lease_store=object(), tenant_admission_backend=object(), tenant_runtime_reconciler=object(), tenant_runtime_fencing_registry=object(), tenant_metrics_store=object(), tenant_migration_lock_backend=object())
    infra = build_runtime_infra(runtime_infra=base, ledger=None, snapshot_store=None, outbox=None, payment_outbox=None, settings_gateway=None, messaging_policy_event_store=None, messaging_policy_read_service=None, delivery_state=None, telegram_outbound_queue=None)
    assert infra.tenant_registry is base.tenant_registry
    assert infra.tenant_runtime_isolation is base.tenant_runtime_isolation
    assert infra.tenant_metrics_store is base.tenant_metrics_store


def test_build_executor_runtime_infra_from_runtime_infra_preserves_tenant_fields():
    base = RuntimeExecutorInfra(tenant_registry=object(), tenant_policy_store=object(), tenant_runtime_lease_store=object())
    infra = build_executor_runtime_infra_from_runtime_infra(runtime_infra=base, delivery_state=None, telegram_outbound_queue=None)
    assert infra.tenant_registry is base.tenant_registry
    assert infra.tenant_policy_store is base.tenant_policy_store
    assert infra.tenant_runtime_lease_store is base.tenant_runtime_lease_store
