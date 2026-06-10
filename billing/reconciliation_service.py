from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from billing.commercial_cycle_contract import ReconciliationDrift
from billing.invoice_lifecycle import CommercialInvoiceEnvelope
from billing.ledger_store import LedgerStoreContract
from billing.usage_rollup import UsageRollup
from core.tenancy.normalization import require_tenant_id
from observability.tenant_metrics_registry import TenantMetricsRegistry
from runtime.monetization import ChargebackRecord, RefundRecord

CANON_BILLING_RECONCILIATION_SERVICE = True


@dataclass(frozen=True)
class ReconciliationReport:
    tenant_id: str
    drifts: tuple[ReconciliationDrift, ...]

    @property
    def is_clean(self) -> bool:
        return not self.drifts


class BillingReconciliationService:
    def __init__(self, *, ledger_store: LedgerStoreContract, metrics: TenantMetricsRegistry | None = None) -> None:
        self._ledger_store = ledger_store
        self._metrics = metrics

    def reconcile(
        self,
        *,
        tenant_id: str,
        invoices: Iterable[CommercialInvoiceEnvelope],
        usage_rollups: Iterable[UsageRollup],
        revenue_account: str = 'billing.accounts.revenue',
        usage_rate_minor_by_meter: Mapping[str, int] | None = None,
        refunds: Iterable[RefundRecord] = (),
        chargebacks: Iterable[ChargebackRecord] = (),
    ) -> ReconciliationReport:
        tid = require_tenant_id(tenant_id)
        drifts: list[ReconciliationDrift] = []
        invoice_total = 0
        usage_total = 0
        rate_map = {str(k): int(v) for k, v in dict(usage_rate_minor_by_meter or {}).items()}
        invoice_currencies: set[str] = set()
        for invoice in invoices:
            invoice.validate()
            if invoice.tenant_id != tid:
                continue
            if invoice.status.value in {'void', 'credited'}:
                continue
            invoice_currencies.add(str(invoice.currency).strip().upper())
            invoice_total += int(invoice.total_minor)
        for rollup in usage_rollups:
            rollup.validate()
            if rollup.tenant_id != tid:
                continue
            usage_total += int(round(float(rollup.quantity) * rate_map.get(rollup.meter_key, 100)))
        ledger_total = self._ledger_store.total_for_account(tenant_id=tid, account_code=revenue_account, side='credit')
        refunded_total = sum(int(item.amount_minor) for item in refunds if str(item.tenant_id) == tid)
        chargeback_total = sum(int(item.amount_minor) for item in chargebacks if str(item.tenant_id) == tid)
        net_expected_total = max(0, invoice_total - refunded_total - chargeback_total)
        ledger_currencies: set[str] = set()
        for posting in self._ledger_store.list_postings(tenant_id=tid):
            for entry in posting.entries:
                if entry.account_code == revenue_account:
                    ledger_currencies.add(str(entry.currency).strip().upper())
        if len(ledger_currencies) > 1:
            drift = ReconciliationDrift(
                tenant_id=tid,
                drift_key='mixed_ledger_currency',
                expected_minor=invoice_total,
                observed_minor=ledger_total,
                delta_minor=ledger_total - invoice_total,
                severity='high',
                details={'owner': 'billing.reconciliation_service', 'currencies': sorted(ledger_currencies), 'account_code': revenue_account},
            )
            drift.validate()
            drifts.append(drift)
        if len(invoice_currencies) > 1:
            drift = ReconciliationDrift(
                tenant_id=tid,
                drift_key='mixed_invoice_currency',
                expected_minor=invoice_total,
                observed_minor=ledger_total,
                delta_minor=ledger_total - invoice_total,
                severity='high',
                details={'owner': 'billing.reconciliation_service', 'currencies': sorted(invoice_currencies)},
            )
            drift.validate()
            drifts.append(drift)
        for key, expected, observed, details in (
            ('invoice_vs_ledger', invoice_total, ledger_total, {'basis': 'issued_invoice_total'}),
            ('net_invoice_vs_ledger', net_expected_total, ledger_total, {'basis': 'issued_invoice_total_minus_refunds_and_chargebacks', 'refunded_total': refunded_total, 'chargeback_total': chargeback_total}),
            ('usage_proxy_vs_ledger', usage_total, ledger_total, {'basis': 'usage_rollup_proxy', 'rate_minor_by_meter': rate_map}),
        ):
            delta = int(observed) - int(expected)
            if delta == 0:
                continue
            severity = 'high' if abs(delta) >= 1000 else 'medium'
            drift = ReconciliationDrift(
                tenant_id=tid,
                drift_key=key,
                expected_minor=int(expected),
                observed_minor=int(observed),
                delta_minor=delta,
                severity=severity,
                details={'owner': 'billing.reconciliation_service', **details},
            )
            drift.validate()
            drifts.append(drift)
        report = ReconciliationReport(tenant_id=tid, drifts=tuple(drifts))
        if self._metrics is not None:
            self._metrics.set_gauge(tenant_id=tid, metric_name='billing_reconciliation_drift_count', value=float(len(report.drifts)))
        return report


__all__ = ['BillingReconciliationService', 'CANON_BILLING_RECONCILIATION_SERVICE', 'ReconciliationReport']
