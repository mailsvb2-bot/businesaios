from __future__ import annotations

"""Thin facade for click economic route operations split by billing boundary."""

from .click_ops_core import (
    export_click_economics_truth,
    get_click_economics_audit,
    get_click_economics_handoff,
    get_click_economics_truth,
)
from .click_ops_billing import (
    export_click_billing_collection_truth,
    export_click_billing_execution_truth,
    export_click_billing_invoice_truth,
    export_click_billing_lifecycle,
    export_click_billing_provider_dispatch_truth,
    export_click_billing_sealed_execution_truth,
    export_click_billing_settlement_truth,
    get_click_billing_collection_audit,
    get_click_billing_collection_truth,
    get_click_billing_execution_audit,
    get_click_billing_execution_truth,
    get_click_billing_invoice_audit,
    get_click_billing_invoice_truth,
    get_click_billing_lifecycle,
    get_click_billing_lifecycle_audit,
    get_click_billing_provider_dispatch_audit,
    get_click_billing_provider_dispatch_truth,
    get_click_billing_sealed_execution_audit,
    get_click_billing_sealed_execution_truth,
    get_click_billing_settlement_audit,
    get_click_billing_settlement_truth,
)

__all__ = [name for name in globals() if name.startswith(("get_click_", "export_click_"))]
