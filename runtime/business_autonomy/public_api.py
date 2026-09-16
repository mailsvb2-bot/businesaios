import os
from hashlib import sha256
from pathlib import Path

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
from runtime.wiring import resolve_storage_config

_STACK: dict | None = None
_STACK_KEY: tuple[str, ...] | None = None


def _operationalization_storage_key() -> tuple[str, ...]:
    storage = resolve_storage_config()
    data_dir = Path(str(os.getenv("DATA_DIR", "data")).strip() or "data").resolve()
    postgres_dsn = str(storage.postgres_dsn or "").strip()
    dsn_fingerprint = sha256(postgres_dsn.encode("utf-8")).hexdigest() if postgres_dsn else ""
    explicit_state_db = str(os.getenv("BUSINESAIOS_BUSINESS_AUTONOMY_STATE_DB", "") or "").strip()
    state_db_key = str(Path(explicit_state_db).resolve()) if explicit_state_db else ""
    return (
        str(data_dir),
        str(storage.env or "").strip().lower(),
        str(storage.backend or "").strip().lower(),
        dsn_fingerprint,
        "1" if storage.postgres_event_store_enabled else "0",
        state_db_key,
        str(os.getenv("BUSINESAIOS_BUSINESS_AUTONOMY_STATE_BACKEND", "sqlite") or "sqlite").strip().lower(),
        str(os.getenv("BUSINESAIOS_RUNTIME_REPLICA_COUNT", "1") or "1").strip(),
    )


def build_business_autonomy_operationalization() -> dict:
    global _STACK, _STACK_KEY
    stack_key = _operationalization_storage_key()
    if _STACK is not None and stack_key == _STACK_KEY:
        return _STACK
    audit_log = PersistentBusinessAutonomyAudit()
    metrics = BusinessAutonomyMetrics(local=InMemoryMetrics(), registry=TenantMetricsRegistry())
    export_service = AuditExportService()
    observability_stores = {"business_autonomy_audit": getattr(audit_log, "_backend", audit_log)}
    dashboard_service = BusinessOpsDashboardService(audit_log=audit_log, metrics=metrics)
    invariant_service = BusinessInvariantEnforcementService(audit_log=audit_log, metrics=metrics)
    chaos_matrix = BusinessRecoveryChaosMatrix()
    guarded_service = build_business_autonomy_guarded_service()
    stack = {
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
    _STACK = stack
    _STACK_KEY = stack_key
    return stack



def _registry_value(root: object, attrs: tuple[str, ...], key: str):
    for attr in attrs:
        root = getattr(root, attr, None)
        if root is None:
            return None
    try:
        return root.get(key)
    except Exception:
        return None


def _business_service(business_id: str, service: object | None):
    requested = str(business_id).strip()
    if service is not None:
        if str(getattr(service, "business_id", "") or "").strip() == requested:
            return service
        existing = _registry_value(
            service,
            ("_autonomy_service", "_autonomy_policy", "_capability_registry"),
            requested,
        )
        if existing is not None and getattr(existing, "capabilities", ()):
            return service
    return build_business_autonomy_guarded_service(
        business_id=requested,
        seed_admin_read_model=True,
    )


def get_registered_business_capabilities(*, business_id: str, service: object | None = None) -> dict:
    entry = _registry_value(_business_service(business_id, service), ("_autonomy_service", "_autonomy_policy", "_capability_registry"), business_id)
    capabilities = [] if entry is None else [{"kind": item.kind.value, "enabled": item.enabled, "confidence": item.confidence, "notes": item.notes} for item in entry.capabilities]
    return {"business_id": business_id, "capabilities": capabilities}


def get_business_trust_profile(*, business_id: str, service: object | None = None) -> dict:
    snapshot = _registry_value(_business_service(business_id, service), ("_trust_policy", "_trust_registry"), business_id)
    if snapshot is None or getattr(snapshot, "business_id", None) != business_id:
        return {"business_id": business_id, "trust_tier": "unknown", "score": 0.0, "reasons": []}
    return {"business_id": snapshot.business_id, "trust_tier": snapshot.trust_tier.value, "score": snapshot.score, "reasons": list(snapshot.reasons), "metadata": dict(snapshot.metadata or {})}


__all__ = ["build_business_autonomy_guarded_service", "build_business_autonomy_operationalization", "get_registered_business_capabilities", "get_business_trust_profile"]
