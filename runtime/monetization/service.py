from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from uuid import uuid4

from runtime.monetization.contracts import (
    ChargebackRecord,
    CheckoutSession,
    InvoiceRecord,
    MonetizationDashboardSnapshot,
    MonetizationPlan,
    RefundRecord,
    SubscriptionRecord,
    TaxBreakdown,
    TaxContext,
    utc_now,
)

CANON_RUNTIME_MONETIZATION_SERVICE = True

_EU_VAT_BPS: dict[str, int] = {
    'NL': 2100,
    'DE': 1900,
    'FR': 2000,
    'BE': 2100,
    'IT': 2200,
    'ES': 2100,
    'PT': 2300,
    'IE': 2300,
}


@dataclass
class InMemoryMonetizationStore:
    plans: dict[str, MonetizationPlan] = field(default_factory=dict)
    checkout_sessions: dict[str, CheckoutSession] = field(default_factory=dict)
    subscriptions: dict[str, SubscriptionRecord] = field(default_factory=dict)
    invoices: dict[str, InvoiceRecord] = field(default_factory=dict)
    refunds: dict[str, RefundRecord] = field(default_factory=dict)
    chargebacks: dict[str, ChargebackRecord] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class UsageInvoiceRequest:
    tenant_id: str
    user_id: str
    plan_id: str
    metered_usage: Mapping[str, float]
    seat_count: int = 0
    tax_context: TaxContext = field(default_factory=lambda: TaxContext(country_code='US'))
    meter_prices: Mapping[str, float] = field(default_factory=dict)
    seat_price: float = 0.0
    subscription_id: str | None = None


class MonetizationService:
    """Canonical monetization owner.

    It does not issue product/business decisions. It only resolves pricing,
    invoices, refunds, chargebacks, and dashboard read models.
    """

    def __init__(self, *, store: InMemoryMonetizationStore | None = None) -> None:
        self._store = store or InMemoryMonetizationStore()

    @property
    def store(self) -> InMemoryMonetizationStore:
        return self._store

    def register_plan(self, plan: MonetizationPlan) -> MonetizationPlan:
        self._store.plans[plan.plan_id] = plan
        return plan

    def create_checkout_session(self, *, tenant_id: str, user_id: str, plan_id: str, success_url: str, cancel_url: str) -> CheckoutSession:
        if plan_id not in self._store.plans:
            raise KeyError(f'unknown plan_id: {plan_id}')
        session_id = str(uuid4())
        session = CheckoutSession(
            session_id=session_id,
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            plan_id=plan_id,
            checkout_url=f'{success_url}?checkout_session_id={session_id}',
            expires_at=utc_now() + timedelta(minutes=30),
            metadata={'cancel_url': str(cancel_url)},
        )
        self._store.checkout_sessions[session_id] = session
        return session

    def activate_subscription(self, *, tenant_id: str, user_id: str, plan_id: str, status: str = 'active', period_days: int = 30) -> SubscriptionRecord:
        if plan_id not in self._store.plans:
            raise KeyError(f'unknown plan_id: {plan_id}')
        record = SubscriptionRecord(
            subscription_id=str(uuid4()),
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            plan_id=plan_id,
            status=str(status),
            current_period_end_at=utc_now() + timedelta(days=max(1, int(period_days))),
        )
        self._store.subscriptions[record.subscription_id] = record
        return record

    def build_usage_invoice(self, request: UsageInvoiceRequest) -> InvoiceRecord:
        plan = self._store.plans[request.plan_id]
        subtotal_minor = self._compute_usage_subtotal_minor(plan=plan, request=request)
        tax = self.resolve_tax(subtotal_minor=subtotal_minor, context=request.tax_context)
        invoice = InvoiceRecord(
            invoice_id=str(uuid4()),
            subscription_id=request.subscription_id,
            tenant_id=str(request.tenant_id),
            user_id=str(request.user_id),
            subtotal_minor=subtotal_minor,
            tax_minor=tax.tax_amount_minor,
            total_minor=subtotal_minor + tax.tax_amount_minor,
            currency=plan.currency,
            status='issued',
            metadata={
                'plan_id': plan.plan_id,
                'regime': tax.regime,
                'reverse_charge_applied': tax.reverse_charge_applied,
                **({'evidence_key': tax.evidence_key} if tax.evidence_key else {}),
            },
        )
        self._store.invoices[invoice.invoice_id] = invoice
        return invoice

    def resolve_tax(self, *, subtotal_minor: int, context: TaxContext) -> TaxBreakdown:
        country = str(context.country_code or '').strip().upper() or 'US'
        if context.is_business_customer and str(context.tax_id or '').strip() and country in _EU_VAT_BPS:
            return TaxBreakdown(
                regime='eu_reverse_charge',
                tax_rate_bps=0,
                tax_amount_minor=0,
                reverse_charge_applied=True,
                evidence_key=f'{country}:{str(context.tax_id).strip().upper()}',
            )
        rate_bps = _EU_VAT_BPS.get(country, 0)
        tax_minor = int(round(int(subtotal_minor) * rate_bps / 10000.0))
        return TaxBreakdown(
            regime='eu_vat_standard' if rate_bps else 'no_tax_default',
            tax_rate_bps=rate_bps,
            tax_amount_minor=tax_minor,
            reverse_charge_applied=False,
        )

    def record_refund(self, *, tenant_id: str, user_id: str, amount_minor: int, currency: str, reason: str) -> RefundRecord:
        record = RefundRecord(
            refund_id=str(uuid4()),
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            amount_minor=max(0, int(amount_minor)),
            currency=str(currency).upper(),
            reason=str(reason),
        )
        self._store.refunds[record.refund_id] = record
        return record

    def record_chargeback(self, *, tenant_id: str, user_id: str, amount_minor: int, currency: str, reason: str) -> ChargebackRecord:
        record = ChargebackRecord(
            chargeback_id=str(uuid4()),
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            amount_minor=max(0, int(amount_minor)),
            currency=str(currency).upper(),
            reason=str(reason),
        )
        self._store.chargebacks[record.chargeback_id] = record
        return record

    def build_dashboard_snapshot(self, *, tenant_id: str, currency: str = 'USD') -> MonetizationDashboardSnapshot:
        normalized_tenant_id = str(tenant_id).strip()
        normalized_currency = str(currency).strip().upper()
        gross = sum(item.total_minor for item in self._store.invoices.values() if item.tenant_id == normalized_tenant_id and item.currency.upper() == normalized_currency and item.status in {'issued', 'paid'})
        refunded = sum(item.amount_minor for item in self._store.refunds.values() if item.tenant_id == normalized_tenant_id and item.currency.upper() == normalized_currency and item.status in {'processed', 'paid', 'completed'})
        chargeback = sum(item.amount_minor for item in self._store.chargebacks.values() if item.tenant_id == normalized_tenant_id and item.currency.upper() == normalized_currency and item.status in {'opened', 'lost', 'won', 'resolved'})
        active = sum(1 for item in self._store.subscriptions.values() if item.tenant_id == normalized_tenant_id and item.status == 'active')
        past_due = sum(1 for item in self._store.subscriptions.values() if item.tenant_id == normalized_tenant_id and item.status == 'past_due')
        cancelled = sum(1 for item in self._store.subscriptions.values() if item.tenant_id == normalized_tenant_id and item.status in {'cancelled', 'canceled'})
        return MonetizationDashboardSnapshot(
            tenant_id=normalized_tenant_id,
            gross_revenue_minor=int(gross),
            refunded_minor=int(refunded),
            chargeback_minor=int(chargeback),
            net_revenue_minor=int(gross) - int(refunded) - int(chargeback),
            active_subscriptions=active,
            past_due_subscriptions=past_due,
            cancelled_subscriptions=cancelled,
            currency=normalized_currency,
        )

    def _compute_usage_subtotal_minor(self, *, plan: MonetizationPlan, request: UsageInvoiceRequest) -> int:
        total = int(plan.amount_minor)
        for meter_key, quantity in dict(request.metered_usage).items():
            used = float(quantity)
            included = float(plan.included_usage.get(str(meter_key), 0.0))
            billable = max(0.0, used - included)
            unit_price = float(request.meter_prices.get(str(meter_key), 0.0))
            total += int(round(billable * unit_price * 100))
        included_seats = max(0, int(plan.included_seats))
        seat_overage = max(0, int(request.seat_count) - included_seats)
        total += int(round(seat_overage * float(request.seat_price) * 100))
        return max(0, total)


__all__ = [
    'CANON_RUNTIME_MONETIZATION_SERVICE',
    'InMemoryMonetizationStore',
    'MonetizationService',
    'UsageInvoiceRequest',
]
