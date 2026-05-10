from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from runtime.platform.billing_recovery_store import SCHEMA_VERSION, PlatformSqliteChargebackStore, PlatformSqliteRefundStore

if TYPE_CHECKING:
    from billing.chargeback_orchestrator import ChargebackCase
    from billing.refund_orchestrator import RefundResult


CANON_BILLING_RECOVERY_STORE = True


class RefundStoreContract(Protocol):
    def save(self, result: 'RefundResult', *, idempotency_key: str | None = None) -> 'RefundResult': ...

    def get_by_idempotency(self, *, tenant_id: str, invoice_id: str, idempotency_key: str) -> 'RefundResult | None': ...

    def list_for_invoice(self, *, tenant_id: str, invoice_id: str) -> tuple['RefundResult', ...]: ...


class ChargebackStoreContract(Protocol):
    def save(self, case: 'ChargebackCase', *, idempotency_key: str | None = None) -> 'ChargebackCase': ...

    def get_by_idempotency(self, *, tenant_id: str, invoice_id: str, idempotency_key: str) -> 'ChargebackCase | None': ...

    def list_for_invoice(self, *, tenant_id: str, invoice_id: str) -> tuple['ChargebackCase', ...]: ...


class SqliteRefundStore(PlatformSqliteRefundStore):
    """Billing-facing refund store facade.

    SQLite ownership lives in runtime.platform.billing_recovery_store.
    """

    def __init__(self, *, sqlite_path: str) -> None:
        from billing.refund_orchestrator import RefundResult

        super().__init__(sqlite_path=sqlite_path, result_cls=RefundResult)


class SqliteChargebackStore(PlatformSqliteChargebackStore):
    """Billing-facing chargeback store facade.

    SQLite ownership lives in runtime.platform.billing_recovery_store.
    """

    def __init__(self, *, sqlite_path: str) -> None:
        from billing.chargeback_orchestrator import ChargebackCase

        super().__init__(sqlite_path=sqlite_path, case_cls=ChargebackCase)


__all__ = [
    'CANON_BILLING_RECOVERY_STORE',
    'ChargebackStoreContract',
    'RefundStoreContract',
    'SCHEMA_VERSION',
    'SqliteChargebackStore',
    'SqliteRefundStore',
]
