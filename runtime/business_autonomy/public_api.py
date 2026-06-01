from __future__ import annotations

from application.business_autonomy.operationalization import (
    BusinessActiveActiveQuorumService,
    BusinessAutonomyMetrics,
    BusinessChaosExecutionService,
    BusinessFinalReadinessReportBuilder,
    BusinessInvariantEnforcementService,
    BusinessObservabilityReportService,
    BusinessOpsDashboardService,
    BusinessRecoveryChaosMatrix,
    BusinessWorkflowRuntimeStub,
)
from application.business_autonomy.persistence import PersistentBusinessAutonomyAudit
from observability.audit_export_service import AuditExportService
from observability.metrics import InMemoryMetrics
from observability.tenant_metrics_registry import TenantMetricsRegistry
from runtime.business_autonomy.bootstrap import build_business_autonomy_guarded_service

_STACK: dict | None = None


def build_business_autonomy_operationalization() -> dict:
    global _STACK
    if _STACK is not None:
        return _STACK
    audit_log = PersistentBusinessAutonomyAudit()
    metrics = BusinessAutonomyMetrics(local=InMemoryMetrics(), registry=TenantMetricsRegistry())
    export_service = AuditExportService()
    observability_stores = {"business_autonomy_audit": getattr(audit_log, "_backend", audit_log)}
    dashboard_service = BusinessOpsDashboardService(audit_log=audit_log, metrics=metrics)
    invariant_service = BusinessInvariantEnforcementService(audit_log=audit_log, metrics=metrics)
    chaos_matrix = BusinessRecoveryChaosMatrix()
    guarded_service = build_business_autonomy_guarded_service()
    _STACK = {
        "audit_log": audit_log,
        "guarded_service": guarded_service,
        "operator_admin_plane": getattr(guarded_service, '_operator_admin_plane', None),
        "workflow_runtime": BusinessWorkflowRuntimeStub(audit_log=audit_log, metrics=metrics),
        "dashboard_service": dashboard_service,
        "observability_report_service": BusinessObservabilityReportService(audit_log=audit_log, metrics=metrics, export_service=export_service, stores=observability_stores),
        "invariant_enforcement_service": invariant_service,
        "chaos_execution_service": BusinessChaosExecutionService(chaos_matrix, audit_log=audit_log, metrics=metrics),
        "active_active_quorum_service": BusinessActiveActiveQuorumService(min_acks=2, audit_log=audit_log, metrics=metrics),
        "metrics": metrics,
        "export_service": export_service,
        "readiness_report_builder": BusinessFinalReadinessReportBuilder(),
        "chaos_matrix": chaos_matrix,
    }
    return _STACK


__all__ = [
    "build_business_autonomy_guarded_service",
    "build_business_autonomy_operationalization",
]
