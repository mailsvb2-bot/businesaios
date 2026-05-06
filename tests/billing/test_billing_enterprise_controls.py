from __future__ import annotations

from billing.connector_usage_meter import ConnectorUsageMeter, ConnectorUsageRecord
from billing.invoice_event_mapper import InvoiceEventMapper
from billing.plan_contract import BillingMeterKey, BillingPlanSpec, PlanQuotaLimit, PlanRateCardItem
from billing.quota_enforcement import QuotaEnforcer
from billing.quota_policy import QuotaPolicyResolver
from billing.tenant_plan_store import InMemoryTenantPlanStore
from billing.usage_meter import InMemoryUsageMeter, UsageRecord
from observability.tenant_metrics_registry import TenantMetricsRegistry
from tenancy import (
    BillingMode,
    InMemoryTenantPolicyStore,
    QuotaDimension,
    TenantAuditScope,
    TenantBillingScope,
    TenantConnectorScope,
    TenantFeatureFlags,
    TenantMemoryScope,
    TenantPlan,
    TenantPolicyBundle,
    TenantQuotaGuard,
    TenantRuntimeLimits,
)


def _bundle(*, tenant_id: str, connector_quota: float = 10.0, allow_overage: bool = False, meter_prices: dict[str, float] | None = None) -> TenantPolicyBundle:
    return TenantPolicyBundle(
        tenant_id=tenant_id,
        feature_flags=TenantFeatureFlags(tenant_id=tenant_id),
        runtime_limits=TenantRuntimeLimits(tenant_id=tenant_id),
        memory_scope=TenantMemoryScope(tenant_id=tenant_id),
        connector_scope=TenantConnectorScope(tenant_id=tenant_id, allowed_connectors=("crm_sync",)),
        audit_scope=TenantAuditScope(tenant_id=tenant_id),
        billing_scope=TenantBillingScope(
            tenant_id=tenant_id,
            mode=BillingMode.POSTPAID,
            currency="USD",
            allow_overage=allow_overage,
            meter_prices=meter_prices or {},
        ),
        quotas={QuotaDimension.CONNECTOR_CALLS_PER_HOUR.value: connector_quota},
    )


def _plan() -> BillingPlanSpec:
    return BillingPlanSpec(
        plan_id=TenantPlan.ENTERPRISE,
        display_name="Enterprise",
        quota_limits=(
            PlanQuotaLimit(
                dimension=QuotaDimension.CONNECTOR_CALLS_PER_HOUR.value,
                limit=100,
                window="hour",
                hard_stop=True,
            ),
        ),
        rate_card=(
            PlanRateCardItem(
                meter_key=BillingMeterKey.CONNECTOR_CALLS,
                unit_price=0.25,
                currency="USD",
                unit_name="call",
                included_units=2,
            ),
        ),
        features={"invoicing": True},
    )


def test_usage_meter_is_idempotent_and_returns_stored_record() -> None:
    meter = InMemoryUsageMeter()
    first = meter.record(UsageRecord(tenant_id="tenant-a", meter_key="api_requests", quantity=3, idempotency_key="k1"))
    second = meter.record(UsageRecord(tenant_id="tenant-a", meter_key="api_requests", quantity=999, idempotency_key="k1"))

    assert first.quantity == 3
    assert second.quantity == 3
    assert meter.total(tenant_id="tenant-a", meter_key="api_requests") == 3


def test_tenant_plan_store_roundtrip_and_unbind() -> None:
    store = InMemoryTenantPlanStore()
    saved_plan = store.save_plan(_plan())
    binding = store.bind(tenant_id="tenant-a", plan_id=saved_plan.plan_id)

    assert store.get_plan("tenant-a") is not None
    assert store.get_binding("tenant-a") == binding
    assert len(store.list_plans()) == 1
    assert len(store.list_bindings()) == 1

    store.unbind("tenant-a")
    assert store.get_plan("tenant-a") is None


def test_quota_policy_resolver_merges_plan_and_tenant_billing_scope() -> None:
    plan_store = InMemoryTenantPlanStore()
    plan_store.save_plan(_plan())
    plan_store.bind(tenant_id="tenant-a", plan_id=TenantPlan.ENTERPRISE)

    policy_store = InMemoryTenantPolicyStore()
    policy_store.save(_bundle(tenant_id="tenant-a", connector_quota=7.0, allow_overage=True))

    resolver = QuotaPolicyResolver(tenant_plan_store=plan_store, tenant_policy_store=policy_store)
    policy = resolver.resolve(tenant_id="tenant-a")

    assert policy.plan_id == TenantPlan.ENTERPRISE.value
    assert policy.limit_for(QuotaDimension.CONNECTOR_CALLS_PER_HOUR.value) == 7.0
    assert policy.allow_overage is True
    assert policy.billing_mode is BillingMode.POSTPAID


def test_quota_enforcer_consumes_and_emits_metrics() -> None:
    plan_store = InMemoryTenantPlanStore()
    plan_store.save_plan(_plan())
    plan_store.bind(tenant_id="tenant-a", plan_id=TenantPlan.ENTERPRISE)

    policy_store = InMemoryTenantPolicyStore()
    policy_store.save(_bundle(tenant_id="tenant-a", connector_quota=2.0))

    meter = InMemoryUsageMeter()
    metrics = TenantMetricsRegistry()
    enforcer = QuotaEnforcer(
        tenant_quota_guard=TenantQuotaGuard(policy_store=policy_store),
        quota_policy=QuotaPolicyResolver(tenant_plan_store=plan_store, tenant_policy_store=policy_store),
        usage_meter=meter,
        metrics=metrics,
    )

    decision = enforcer.consume(
        tenant_id="tenant-a",
        dimension=QuotaDimension.CONNECTOR_CALLS_PER_HOUR.value,
        amount=1.0,
        meter_key=BillingMeterKey.CONNECTOR_CALLS,
        idempotency_key="op-1",
        labels={"connector_id": "crm_sync"},
    )

    assert decision.allowed is True
    assert decision.metered is True
    assert meter.total(tenant_id="tenant-a", meter_key=BillingMeterKey.CONNECTOR_CALLS) == 1.0
    snapshot = metrics.snapshot(tenant_id="tenant-a")
    assert "billing.quota.requests" in snapshot
    assert f"billing.quota.used.{QuotaDimension.CONNECTOR_CALLS_PER_HOUR.value}" in snapshot


def test_connector_usage_meter_does_not_double_count_when_enforcer_present() -> None:
    plan_store = InMemoryTenantPlanStore()
    plan_store.save_plan(_plan())
    plan_store.bind(tenant_id="tenant-a", plan_id=TenantPlan.ENTERPRISE)

    policy_store = InMemoryTenantPolicyStore()
    policy_store.save(_bundle(tenant_id="tenant-a", connector_quota=2.0))

    meter = InMemoryUsageMeter()
    enforcer = QuotaEnforcer(
        tenant_quota_guard=TenantQuotaGuard(policy_store=policy_store),
        quota_policy=QuotaPolicyResolver(tenant_plan_store=plan_store, tenant_policy_store=policy_store),
        usage_meter=meter,
    )
    connector_meter = ConnectorUsageMeter(usage_meter=meter, quota_enforcer=enforcer)

    first = connector_meter.record(
        ConnectorUsageRecord(
            tenant_id="tenant-a",
            connector_id="crm_sync",
            operation="sync_customer",
            idempotency_key="connector-op-1",
        )
    )
    second = connector_meter.record(
        ConnectorUsageRecord(
            tenant_id="tenant-a",
            connector_id="crm_sync",
            operation="sync_customer",
            idempotency_key="connector-op-1",
        )
    )

    assert first.idempotency_key == "connector-op-1"
    assert second.idempotency_key == "connector-op-1"
    assert meter.total(tenant_id="tenant-a", meter_key=BillingMeterKey.CONNECTOR_CALLS) == 1.0


def test_connector_usage_meter_blocks_exceeded_quota() -> None:
    plan_store = InMemoryTenantPlanStore()
    plan_store.save_plan(_plan())
    plan_store.bind(tenant_id="tenant-a", plan_id=TenantPlan.ENTERPRISE)

    policy_store = InMemoryTenantPolicyStore()
    policy_store.save(_bundle(tenant_id="tenant-a", connector_quota=1.0))

    meter = InMemoryUsageMeter()
    enforcer = QuotaEnforcer(
        tenant_quota_guard=TenantQuotaGuard(policy_store=policy_store),
        quota_policy=QuotaPolicyResolver(tenant_plan_store=plan_store, tenant_policy_store=policy_store),
        usage_meter=meter,
    )
    connector_meter = ConnectorUsageMeter(usage_meter=meter, quota_enforcer=enforcer)

    connector_meter.record(
        ConnectorUsageRecord(
            tenant_id="tenant-a",
            connector_id="crm_sync",
            operation="sync_customer",
            idempotency_key="connector-op-1",
        )
    )

    try:
        connector_meter.record(
            ConnectorUsageRecord(
                tenant_id="tenant-a",
                connector_id="crm_sync",
                operation="sync_customer",
                idempotency_key="connector-op-2",
            )
        )
    except PermissionError as exc:
        assert "connector quota exceeded" in str(exc)
    else:
        raise AssertionError("expected PermissionError")


def test_invoice_event_mapper_applies_plan_and_billing_scope_override() -> None:
    mapper = InvoiceEventMapper()
    plan = _plan()
    record = UsageRecord(
        tenant_id="tenant-a",
        meter_key=BillingMeterKey.CONNECTOR_CALLS,
        quantity=5,
        idempotency_key="usage-1",
        metadata={"resource_id": "crm:sync:1"},
    )
    billing_scope = TenantBillingScope(
        tenant_id="tenant-a",
        currency="EUR",
        meter_prices={BillingMeterKey.CONNECTOR_CALLS: 1.5},
    )

    line = mapper.build_line_item(record=record, plan=plan, billing_scope=billing_scope)
    event = mapper.build_billable_event(record=record, plan=plan, billing_scope=billing_scope)

    assert line is not None
    assert line.currency == "EUR"
    assert line.amount == 4.5
    assert event is not None
    assert event.amount == 4.5
    assert event.currency == "EUR"



def test_plan_quota_is_enforced_even_without_tenant_policy_quota() -> None:
    plan_store = InMemoryTenantPlanStore()
    plan_store.save_plan(_plan())
    plan_store.bind(tenant_id="tenant-a", plan_id=TenantPlan.ENTERPRISE)

    policy_store = InMemoryTenantPolicyStore()
    policy_store.save(_bundle(tenant_id="tenant-a", connector_quota=1000.0))

    meter = InMemoryUsageMeter()
    enforcer = QuotaEnforcer(
        tenant_quota_guard=TenantQuotaGuard(policy_store=policy_store),
        quota_policy=QuotaPolicyResolver(tenant_plan_store=plan_store, tenant_policy_store=policy_store),
        usage_meter=meter,
    )

    # override binding to a smaller commercial ceiling than the tenant bundle
    binding = plan_store.get_binding("tenant-a")
    assert binding is not None
    plan_store.save_binding(
        binding.normalized_copy().__class__(
            tenant_id=binding.tenant_id,
            plan_id=binding.plan_id,
            bound_at=binding.bound_at,
            effective_from=binding.effective_from,
            overrides={"quota_limits": {QuotaDimension.CONNECTOR_CALLS_PER_HOUR.value: 1.0}},
        )
    )

    first = enforcer.consume(
        tenant_id="tenant-a",
        dimension=QuotaDimension.CONNECTOR_CALLS_PER_HOUR.value,
        amount=1.0,
        meter_key=BillingMeterKey.CONNECTOR_CALLS,
        idempotency_key="plan-only-1",
    )
    second = enforcer.consume(
        tenant_id="tenant-a",
        dimension=QuotaDimension.CONNECTOR_CALLS_PER_HOUR.value,
        amount=1.0,
        meter_key=BillingMeterKey.CONNECTOR_CALLS,
        idempotency_key="plan-only-2",
    )

    assert first.allowed is True
    assert second.allowed is False
    assert second.limit == 1.0



def test_allow_overage_applies_for_non_hard_stop_dimensions() -> None:
    plan_store = InMemoryTenantPlanStore()
    soft_plan = BillingPlanSpec(
        plan_id=TenantPlan.ENTERPRISE,
        display_name="Enterprise Soft",
        quota_limits=(
            PlanQuotaLimit(
                dimension=QuotaDimension.CONNECTOR_CALLS_PER_HOUR.value,
                limit=1,
                window="hour",
                hard_stop=False,
            ),
        ),
    )
    plan_store.save_plan(soft_plan)
    plan_store.bind(tenant_id="tenant-a", plan_id=TenantPlan.ENTERPRISE)

    policy_store = InMemoryTenantPolicyStore()
    policy_store.save(_bundle(tenant_id="tenant-a", connector_quota=100.0, allow_overage=True))

    meter = InMemoryUsageMeter()
    enforcer = QuotaEnforcer(
        tenant_quota_guard=TenantQuotaGuard(policy_store=policy_store),
        quota_policy=QuotaPolicyResolver(tenant_plan_store=plan_store, tenant_policy_store=policy_store),
        usage_meter=meter,
    )
    binding = plan_store.get_binding("tenant-a")
    assert binding is not None
    plan_store.save_binding(
        binding.normalized_copy().__class__(
            tenant_id=binding.tenant_id,
            plan_id=binding.plan_id,
            bound_at=binding.bound_at,
            effective_from=binding.effective_from,
            overrides={"quota_limits": {QuotaDimension.CONNECTOR_CALLS_PER_HOUR.value: 1.0}},
        )
    )

    first = enforcer.consume(
        tenant_id="tenant-a",
        dimension=QuotaDimension.CONNECTOR_CALLS_PER_HOUR.value,
        amount=1.0,
        meter_key=BillingMeterKey.CONNECTOR_CALLS,
        idempotency_key="overage-1",
    )
    second = enforcer.consume(
        tenant_id="tenant-a",
        dimension=QuotaDimension.CONNECTOR_CALLS_PER_HOUR.value,
        amount=1.0,
        meter_key=BillingMeterKey.CONNECTOR_CALLS,
        idempotency_key="overage-2",
    )

    assert first.allowed is True
    assert second.allowed is True
    assert second.reason == "overage allowed"
    assert second.metadata["overage_amount"] == 1.0
