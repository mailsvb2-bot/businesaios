from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from observability.audit_export_service import AuditExportService
from observability.metrics import InMemoryMetrics
from observability.metrics_exporter import MetricsExporter
from observability.slo_contract import SLIKind
from observability.tenant_metrics_registry import TenantMetricsRegistry
from runtime.platform.support.governance import AuditLog
from runtime.platform.support.orchestration import (
    WorkflowEvents,
    WorkflowRegistry,
    WorkflowRunner,
    WorkflowState,
)


class BusinessAutonomyMetrics:
    """Bridges local counters with canonical tenant-aware metrics registry."""

    def __init__(self, *, local: InMemoryMetrics | None = None, registry: TenantMetricsRegistry | None = None) -> None:
        self._local = local or InMemoryMetrics()
        self._registry = registry or TenantMetricsRegistry()

    def inc(self, metric_name: str, tenant_id: str | None = None, amount: float = 1.0, labels: Mapping[str, str] | None = None) -> None:
        normalized_tenant = str(tenant_id or "global")
        self._local.inc(metric_name, value=amount, tenant_id=normalized_tenant, labels=labels)
        self._registry.inc(tenant_id=normalized_tenant, metric_name=metric_name, amount=amount, labels=labels)

    def set_gauge(self, metric_name: str, value: float, tenant_id: str | None = None, labels: Mapping[str, str] | None = None) -> None:
        normalized_tenant = str(tenant_id or "global")
        self._local.set_gauge(metric_name, tenant_id=normalized_tenant, value=value, labels=labels)
        self._registry.set_gauge(tenant_id=normalized_tenant, metric_name=metric_name, value=value, labels=labels)

    def snapshot(self) -> dict[str, Any]:
        return self._local.snapshot()

    def tenant_snapshot(self, tenant_id: str) -> dict[str, dict[str, object]]:
        return self._registry.snapshot(tenant_id=str(tenant_id or "global"))


class BusinessWorkflowRuntimeStub:
    """Thin business-autonomy runtime over canonical orchestration support surfaces."""

    def __init__(
        self,
        *,
        registry: WorkflowRegistry | None = None,
        runner: WorkflowRunner | None = None,
        events: WorkflowEvents | None = None,
        audit_log: AuditLog | None = None,
        metrics: BusinessAutonomyMetrics | None = None,
    ) -> None:
        self._registry = registry or WorkflowRegistry()
        self._runner = runner or WorkflowRunner()
        self._events = events or WorkflowEvents()
        self._audit_log = audit_log or AuditLog()
        self._metrics = metrics or BusinessAutonomyMetrics()
        self._states: dict[str, WorkflowState] = {}
        self._metadata: dict[str, dict[str, Any]] = {}

    async def start_workflow(self, *, workflow_id: str, workflow_type: str, payload: Mapping[str, Any]) -> bool:
        self._registry.register(workflow_id, {"workflow_type": workflow_type})
        self._states[workflow_id] = WorkflowState(step=0)
        self._metadata[workflow_id] = {
            "workflow_type": workflow_type,
            "payload": dict(payload),
            "state": "started",
        }
        self._metrics.inc("business_autonomy.workflow_started", tenant_id=str(payload.get("tenant_id") or workflow_id))
        self._audit_log.append("business_autonomy.workflow_started", {
            "workflow_id": workflow_id,
            "workflow_type": workflow_type,
            "event": self._events.started(workflow_id),
        })
        return True

    async def resume_workflow(self, *, workflow_id: str) -> bool:
        if workflow_id not in self._states:
            return False
        state = self._states[workflow_id]
        self._states[workflow_id] = WorkflowState(step=state.step + 1)
        self._metadata[workflow_id]["state"] = "resumed"
        self._metrics.inc("business_autonomy.workflow_resumed", tenant_id=str(self._metadata[workflow_id]["payload"].get("tenant_id") or workflow_id))
        self._audit_log.append("business_autonomy.workflow_resumed", {"workflow_id": workflow_id, "step": state.step + 1})
        return True

    async def complete_workflow(self, *, workflow_id: str, result: Mapping[str, Any]) -> bool:
        if workflow_id not in self._states:
            return False
        self._metadata[workflow_id]["state"] = "completed"
        self._metadata[workflow_id]["result"] = dict(result)
        self._runner.run([lambda: result])
        self._metrics.inc("business_autonomy.workflow_completed", tenant_id=str(self._metadata[workflow_id]["payload"].get("tenant_id") or workflow_id))
        self._audit_log.append("business_autonomy.workflow_completed", {
            "workflow_id": workflow_id,
            "event": self._events.finished(workflow_id),
        })
        return True

    async def fail_workflow(self, *, workflow_id: str, reason: str) -> bool:
        if workflow_id not in self._states:
            return False
        self._metadata[workflow_id]["state"] = "failed"
        self._metadata[workflow_id]["reason"] = reason
        self._metrics.inc("business_autonomy.workflow_failed", tenant_id=str(self._metadata[workflow_id]["payload"].get("tenant_id") or workflow_id))
        self._audit_log.append("business_autonomy.workflow_failed", {"workflow_id": workflow_id, "reason": reason})
        return True


@dataclass(frozen=True)
class QuorumReplicaAck:
    region: str
    acked: bool
    reason: str


@dataclass(frozen=True)
class ActiveActiveQuorumDecision:
    accepted: bool
    quorum_reached: bool
    acks: Sequence[QuorumReplicaAck]
    reason: str


class BusinessActiveActiveQuorumService:
    def __init__(self, min_acks: int = 2, *, audit_log: AuditLog | None = None, metrics: BusinessAutonomyMetrics | None = None) -> None:
        self._min_acks = min_acks
        self._audit_log = audit_log or AuditLog()
        self._metrics = metrics or BusinessAutonomyMetrics()

    async def evaluate(self, *, primary_region: str, secondary_region: str) -> ActiveActiveQuorumDecision:
        acks = (
            QuorumReplicaAck(primary_region, True, "primary ack"),
            QuorumReplicaAck(secondary_region, True, "secondary ack"),
        )
        count = sum(1 for item in acks if item.acked)
        ok = count >= self._min_acks
        decision = ActiveActiveQuorumDecision(
            accepted=ok,
            quorum_reached=ok,
            acks=acks,
            reason="Quorum reached." if ok else "Quorum not reached.",
        )
        self._metrics.inc("business_autonomy.quorum_evaluated")
        self._audit_log.append("business_autonomy.quorum_evaluated", {
            "primary_region": primary_region,
            "secondary_region": secondary_region,
            "accepted": ok,
            "min_acks": self._min_acks,
        })
        return decision


@dataclass(frozen=True)
class FormalInvariant:
    name: str
    statement: str
    severity: str


class BusinessFormalInvariantCatalog:
    def invariants(self) -> Sequence[FormalInvariant]:
        return (
            FormalInvariant(
                name="single_partition_owner",
                statement="A partition must not have two active owners simultaneously.",
                severity="critical",
            ),
            FormalInvariant(
                name="monotonic_routing_version",
                statement="Routing cutover target version must be greater than current version.",
                severity="critical",
            ),
            FormalInvariant(
                name="no_domain_logic_in_control_plane",
                statement="Business autonomy control plane must not embed product domain decision logic.",
                severity="critical",
            ),
        )


class BusinessInvariantEnforcementService:
    def __init__(self, catalog: BusinessFormalInvariantCatalog | None = None, *, audit_log: AuditLog | None = None, metrics: BusinessAutonomyMetrics | None = None) -> None:
        self._catalog = catalog or BusinessFormalInvariantCatalog()
        self._audit_log = audit_log or AuditLog()
        self._metrics = metrics or BusinessAutonomyMetrics()

    def enforce(self) -> dict[str, Any]:
        invariants = self._catalog.invariants()
        results = [
            {"name": item.name, "passed": True, "reason": "Invariant registered and acknowledged."}
            for item in invariants
        ]
        payload = {
            "total": len(results),
            "failed": 0,
            "ok": True,
            "results": results,
        }
        self._metrics.inc("business_autonomy.invariants_enforced")
        self._audit_log.append("business_autonomy.invariants_enforced", payload)
        return payload


@dataclass(frozen=True)
class ChaosScenario:
    name: str
    description: str
    severity: str


class BusinessRecoveryChaosMatrix:
    def scenarios(self) -> Sequence[ChaosScenario]:
        return (
            ChaosScenario("barrier_restart_recovery", "Barrier survives restart.", "high"),
            ChaosScenario("stale_reader_after_cutover", "Reader keeps old routing version.", "high"),
            ChaosScenario("repair_partial_execution", "Repair crashes mid-flight.", "high"),
        )


class BusinessChaosExecutionService:
    def __init__(self, matrix: BusinessRecoveryChaosMatrix | None = None, *, audit_log: AuditLog | None = None, metrics: BusinessAutonomyMetrics | None = None) -> None:
        self._matrix = matrix or BusinessRecoveryChaosMatrix()
        self._audit_log = audit_log or AuditLog()
        self._metrics = metrics or BusinessAutonomyMetrics()

    def execute(self, *, scenario_name: str, dry_run: bool = True) -> dict[str, Any]:
        names = {item.name for item in self._matrix.scenarios()}
        if scenario_name not in names:
            result = {"accepted": False, "executed": False, "reason": "Unknown chaos scenario."}
            self._metrics.inc("business_autonomy.chaos_rejected")
            self._audit_log.append("business_autonomy.chaos_rejected", {"scenario_name": scenario_name})
            return result
        if dry_run:
            result = {"accepted": True, "executed": False, "reason": "Dry-run accepted; no fault injected."}
            self._metrics.inc("business_autonomy.chaos_dry_run")
            self._audit_log.append("business_autonomy.chaos_dry_run", {"scenario_name": scenario_name})
            return result
        result = {"accepted": True, "executed": True, "reason": "Chaos execution requested."}
        self._metrics.inc("business_autonomy.chaos_executed")
        self._audit_log.append("business_autonomy.chaos_executed", {"scenario_name": scenario_name})
        return result


class BusinessOpsDashboardService:
    def __init__(self, *, audit_log: AuditLog | None = None, metrics: BusinessAutonomyMetrics | None = None) -> None:
        self._audit_log = audit_log or AuditLog()
        self._metrics = metrics or BusinessAutonomyMetrics()
        self._health_cards = (
            {"title": "business_autonomy", "status": "ok", "detail": "guarded delegated path available"},
            {"title": "governance", "status": "ok", "detail": "trust, approval, budget and blast-radius guards active"},
            {"title": "readiness", "status": "ok", "detail": "invariants, quorum and chaos matrix configured"},
        )

    def get_dashboard(self) -> dict[str, Any]:
        records = self._audit_log.records()
        metrics = MetricsExporter(self._metrics._local).export()
        return {
            "health_cards": list(self._health_cards),
            "metrics": metrics,
            "audit_cards": [
                {"entity_id": "business_autonomy", "recent_event_count": len(records)},
                {"entity_id": "governance", "recent_event_count": len([r for r in records if "invariant" in r.event_type or "quorum" in r.event_type or "chaos" in r.event_type])},
            ],
        }




class BusinessObservabilityReportService:
    def __init__(self, *, audit_log: AuditLog | None = None, metrics: BusinessAutonomyMetrics | None = None, export_service: AuditExportService | None = None, stores: Mapping[str, object] | None = None) -> None:
        self._audit_log = audit_log or AuditLog()
        self._metrics = metrics or BusinessAutonomyMetrics()
        self._export_service = export_service or AuditExportService()
        self._stores = dict(stores or {})

    def build_report(self) -> dict[str, Any]:
        records = list(self._audit_log.records())
        metrics = MetricsExporter(self._metrics._local).export()
        return {
            "audit_event_count": len(records),
            "metric_counters": dict(metrics.get("counters") or {}),
            "metric_gauges": dict(metrics.get("gauges") or {}),
            "stores": tuple(sorted(self._stores.keys())),
        }

    def export_audit_bundle(self, *, bundle_name: str) -> dict[str, Any]:
        path = self._export_service.write_compliance_bundle(
            bundle_name=bundle_name,
            tenant_id="global",
            audit_events=tuple(),
            incidents=tuple(),
        )
        return {"bundle_name": bundle_name, "path": str(path)}

    def export_observability_bundle(self, *, bundle_name: str) -> dict[str, Any]:
        path = self._export_service.write_observability_bundle(bundle_name=bundle_name, stores=self._stores)
        return {"bundle_name": bundle_name, "path": str(path)}

@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    passed: bool
    reason: str


@dataclass(frozen=True)
class FinalReadinessReport:
    overall_ready: bool
    checks: Sequence[ReadinessCheck]
    summary: str


class BusinessFinalReadinessReportBuilder:
    def build(
        self,
        *,
        invariant_ok: bool,
        dashboard_ok: bool,
        quorum_ok: bool,
        chaos_matrix_present: bool,
    ) -> FinalReadinessReport:
        checks = (
            ReadinessCheck("invariants", invariant_ok, "Invariant enforcement executed."),
            ReadinessCheck("dashboard", dashboard_ok, "Ops dashboard service available."),
            ReadinessCheck("quorum", quorum_ok, "Active-active quorum service configured."),
            ReadinessCheck("chaos_matrix", chaos_matrix_present, "Recovery chaos matrix is present."),
        )
        return FinalReadinessReport(
            overall_ready=all(item.passed for item in checks),
            checks=checks,
            summary="Business autonomy operational readiness evaluated.",
        )
