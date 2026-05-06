from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module

from runtime.economic_core import EconomicAdminReadService
from entrypoints.api.economic_routes import service as economic_service

CANON_ECONOMIC_ROUTE_HANDLERS = True


def _economic_executor_exports() -> tuple[object, object]:
    module = import_module("runtime.executor")
    return (
        getattr(module, "build_click_provider_dispatch_execution_contract"),
        getattr(module, "build_spend_runtime_execution_contract"),
    )


(
    build_click_provider_dispatch_execution_contract,
    build_spend_runtime_execution_contract,
) = _economic_executor_exports()


@dataclass(frozen=True, slots=True)
class EconomicRouteHandlers:
    client_outcome_handlers: object
    admin_read_service: EconomicAdminReadService

    def _build_client_outcome_payloads(self, *, order_id: str, lead_id: str):
        return economic_service._build_client_outcome_payloads(self, order_id=order_id, lead_id=lead_id)

    def _build_client_outcome_truth(self, *, order_id: str, lead_id: str):
        return economic_service._build_client_outcome_truth(self, order_id=order_id, lead_id=lead_id)

    def _build_business_truth(self, *, order_id: str, lead_id: str):
        return economic_service._build_business_truth(self, order_id=order_id, lead_id=lead_id)


def build_economic_route_handlers(*, client_outcome_handlers: object) -> EconomicRouteHandlers:
    return EconomicRouteHandlers(
        client_outcome_handlers=client_outcome_handlers,
        admin_read_service=EconomicAdminReadService(),
    )


for _name in [
    'get_click_economics_truth','get_spend_truth','export_click_economics_truth','export_spend_truth',
    'get_click_economics_audit','get_spend_audit','get_click_economics_handoff','get_click_billing_invoice_truth',
    'export_click_billing_invoice_truth','get_click_billing_invoice_audit','get_click_billing_collection_truth',
    'export_click_billing_collection_truth','get_click_billing_collection_audit','get_click_billing_execution_truth',
    'export_click_billing_execution_truth','get_click_billing_settlement_truth','export_click_billing_settlement_truth',
    'get_click_billing_settlement_audit','get_click_billing_execution_audit','get_click_billing_provider_dispatch_truth',
    'export_click_billing_provider_dispatch_truth','get_click_billing_provider_dispatch_audit',
    'get_spend_external_runtime_request_truth','export_spend_external_runtime_request_truth',
    'get_spend_external_runtime_request_audit','get_click_billing_sealed_execution_truth',
    'export_click_billing_sealed_execution_truth','get_click_billing_sealed_execution_audit',
    'get_spend_external_sealed_execution_truth','export_spend_external_sealed_execution_truth',
    'get_spend_external_sealed_execution_audit','get_business_cross_domain_reconciliation',
    'get_click_billing_lifecycle','export_click_billing_lifecycle','get_click_billing_lifecycle_audit',
    'get_spend_manifest','get_spend_source_ingress_truth','export_spend_source_ingress_truth',
    'get_spend_source_ingress_audit','get_spend_ingress_envelope_truth','export_spend_ingress_envelope_truth',
    'get_spend_external_ingress_truth','export_spend_external_ingress_truth','get_spend_external_ingress_audit',
    'get_spend_ingress_envelope_audit','get_spend_source_truth','export_spend_source_truth',
    'get_spend_source_audit','get_spend_source_manifest','get_client_outcome_truth','export_client_outcome_truth',
    'get_business_truth','export_business_truth','get_client_outcome_anomalies','get_business_audit',
    'get_client_outcome_audit','get_business_anomalies',
]:
    if hasattr(economic_service, _name):
        setattr(EconomicRouteHandlers, _name, getattr(economic_service, _name))
