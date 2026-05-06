from __future__ import annotations

from decimal import Decimal
from typing import Any

from core.economics.types import EconomicsSnapshot
from core.finance.strategic.decimal_utils import q2, quantize_rate, to_decimal
from core.finance.strategic.input.financial_input_builder import FinancialInputBuilder
from core.finance.strategic.types import FinancialInput


class EconomicsSnapshotToFinancialInputAdapter:
    """Canonical seam: economics snapshot or raw envelope -> strategic finance input.

    This is the only adapter allowed to translate host economics snapshots into
    the finance bounded context. Compatibility imports must route here instead
    of maintaining their own transformation logic.
    """

    def __init__(self, builder: FinancialInputBuilder | None = None) -> None:
        self._builder = builder or FinancialInputBuilder()

    def build(
        self,
        source: EconomicsSnapshot | dict[str, Any],
        *,
        correlation_id: str | None = None,
        tenant_id: str | None = None,
        assumption_overrides: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> FinancialInput:
        if isinstance(source, dict):
            snapshot = source.get("economics_snapshot")
            if snapshot is not None:
                return self.build(
                    snapshot,
                    correlation_id=str(correlation_id or source.get("correlation_id") or "strategic-finance"),
                    tenant_id=str(tenant_id or source.get("tenant_id") or "default"),
                    assumption_overrides=dict(assumption_overrides or source.get("assumption_overrides") or {}),
                    metadata=dict(metadata or source.get("metadata") or {}),
                )
            return self._builder.build(source)

        snapshot = source
        rm = snapshot.read_model
        unit = snapshot.unit_economics
        margin = snapshot.margin
        merged_metadata = dict(metadata or {})
        merged_metadata.setdefault('economics_snapshot_id', str(snapshot.snapshot_id))
        merged_metadata.setdefault('has_blocking_guard', snapshot.has_blocking_guard)
        merged_metadata.setdefault('source', 'core.economics.snapshot')
        merged_metadata.setdefault('margin_status', getattr(snapshot.margin.status, 'value', str(snapshot.margin.status)))
        merged_metadata.setdefault('budget_pressure_level', getattr(snapshot.budget_envelope.pressure_level, 'value', str(snapshot.budget_envelope.pressure_level)))
        payload = {
            'tenant_id': str(tenant_id or snapshot.metadata.get('tenant_id') or snapshot.snapshot_id),
            'correlation_id': str(correlation_id or snapshot.metadata.get('correlation_id') or snapshot.snapshot_id),
            'period_months': max(1, int(getattr(rm.revenue, 'period_days', 30) // 30) or 1),
            'revenue': q2(rm.revenue.net_revenue),
            'costs': q2(rm.cost.cogs + rm.cost.fixed_costs + rm.cost.variable_costs),
            'cash': q2(rm.cashflow.unrestricted_cash),
            'debt': q2(snapshot.metadata.get('debt') or merged_metadata.get('debt') or Decimal('0')),
            'customers': int(rm.customer_value.active_customers),
            'new_customers': int(rm.customer_value.new_customers),
            'churn_rate': quantize_rate(Decimal('1') - to_decimal(rm.customer_value.gross_retention_30d)),
            'gross_margin_rate': quantize_rate(to_decimal(margin.gross_margin_ratio)),
            'growth_rate': quantize_rate(to_decimal(snapshot.metadata.get('growth_rate') or merged_metadata.get('growth_rate') or 0)),
            'channel_spend': {
                'marketing': q2(rm.spend.marketing_spend),
                'sales': q2(rm.spend.sales_spend),
                'operations': q2(rm.spend.operations_spend),
            },
            'channel_new_customers': {'blended': int(rm.customer_value.new_customers)},
            'assumptions': {
                'gross_margin_rate': quantize_rate(to_decimal(margin.gross_margin_ratio)),
                'contribution_margin_ratio': quantize_rate(to_decimal(unit.contribution_margin_ratio)),
                **{str(k): to_decimal(v) for k, v in dict(assumption_overrides or {}).items()},
            },
            'metadata': merged_metadata,
        }
        return self._builder.build(payload)


def build_economics_snapshot_adapter(
    builder: FinancialInputBuilder | None = None,
) -> EconomicsSnapshotToFinancialInputAdapter:
    return EconomicsSnapshotToFinancialInputAdapter(builder=builder)
