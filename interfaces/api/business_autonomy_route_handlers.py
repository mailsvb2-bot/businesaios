"""Canonical route handlers for business autonomy operational visibility."""

from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping

from application.business_autonomy.delayed_outcome_bridge import BusinessAutonomyDelayedOutcomeBridge
from application.business_autonomy.safety_core import build_safety_core_admin_surface
from runtime.business_autonomy.bootstrap import build_business_autonomy_guarded_service
from runtime.business_autonomy.public_api import (
    build_business_autonomy_operationalization,
    get_business_trust_profile,
    get_registered_business_capabilities,
)
from runtime.demand_gravity.admin_view import build_demand_gravity_admin_view

CANON_API_BUSINESS_AUTONOMY_ROUTE_HANDLERS = True
CANON_API_BUSINESS_AUTONOMY_ROUTE_HANDLERS_FINAL_OWNER = "interfaces.api.business_autonomy_route_handlers"


def _default_stack() -> dict[str, Any]:
    return build_business_autonomy_operationalization()


@dataclass(frozen=True)
class BusinessAutonomyRouteHandlers:
    stack: Mapping[str, Any] = field(default_factory=_default_stack)

    def get_dashboard(self) -> dict[str, Any]:
        service = self.stack["dashboard_service"]
        return dict(service.get_dashboard())

    def get_readiness(self) -> dict[str, Any]:
        invariant_result = self.stack["invariant_enforcement_service"].enforce()
        dashboard = self.stack["dashboard_service"].get_dashboard()
        quorum_ok = bool(getattr(self.stack.get("active_active_quorum_service"), "_min_acks", 0) >= 2)
        chaos_matrix_present = bool(self.stack["chaos_matrix"].scenarios())
        report = self.stack["readiness_report_builder"].build(
            invariant_ok=bool(invariant_result.get("ok", False)),
            dashboard_ok=bool(dashboard.get("health_cards")),
            quorum_ok=quorum_ok,
            chaos_matrix_present=chaos_matrix_present,
        )
        return {
            "overall_ready": report.overall_ready,
            "summary": report.summary,
            "checks": [{"name": item.name, "passed": item.passed, "reason": item.reason} for item in report.checks],
        }

    def get_audit(self, limit: int = 100) -> dict[str, Any]:
        all_records = list(self.stack["audit_log"].records())
        records = all_records[-max(0, int(limit)):] if limit >= 0 else all_records
        return {
            "records": [
                {"event_type": item.event_type, "payload": dict(item.payload), "created_at_utc": getattr(item, "created_at_utc", "")}
                for item in records
            ],
            "count": len(records),
        }

    def run_chaos_dry_run(self, scenario_name: str) -> dict[str, Any]:
        return dict(self.stack["chaos_execution_service"].execute(scenario_name=scenario_name, dry_run=True))

    def get_observability_report(self) -> dict[str, Any]:
        service = self.stack["observability_report_service"]
        return dict(service.build_report())

    def export_observability_bundle(self, bundle_name: str = "business-autonomy") -> dict[str, Any]:
        service = self.stack["observability_report_service"]
        return dict(service.export_observability_bundle(bundle_name=bundle_name))

    def export_audit_bundle(self, bundle_name: str = "business-autonomy-audit") -> dict[str, Any]:
        service = self.stack["observability_report_service"]
        return dict(service.export_audit_bundle(bundle_name=bundle_name))

    def get_fleet_view(self, limit: int = 100) -> dict[str, Any]:
        plane = self.stack.get("operator_admin_plane")
        if plane is None:
            return {"fleet_cards": [], "business_class_rows": [], "trust_capability_rows": [], "approval_bottlenecks": [], "cross_business_failures": [], "delayed_outcome_quarantine_rows": [], "export_surface": {}}
        view = plane.get_fleet_view(limit=limit)
        return {
            "fleet_cards": [{"title": card.title, "value": card.value, "status": card.status, "detail": card.detail} for card in view.fleet_cards],
            "business_class_rows": [dict(item) for item in view.business_class_rows],
            "trust_capability_rows": [dict(item) for item in view.trust_capability_rows],
            "approval_bottlenecks": [dict(item) for item in view.approval_bottlenecks],
            "cross_business_failures": [dict(item) for item in view.cross_business_failures],
            "delayed_outcome_quarantine_rows": [dict(item) for item in getattr(view, "delayed_outcome_quarantine_rows", ())],
            "export_surface": dict(view.export_surface),
        }

    def get_safety_core_surface(self, *, rust_available: bool = False, mode: str = "python_mirror") -> dict[str, Any]:
        return dict(build_safety_core_admin_surface(rust_available=rust_available, mode=mode))

    def get_demand_gravity_surface(self, *, tenant_id: str, candidates: tuple[Any, ...] = (), decision_refs: tuple[str, ...] = ()) -> dict[str, Any]:
        return dict(build_demand_gravity_admin_view(tenant_id=tenant_id, candidates=candidates, decision_refs=decision_refs))

    def _delayed_outcome_bridge(self) -> BusinessAutonomyDelayedOutcomeBridge:
        return BusinessAutonomyDelayedOutcomeBridge.default()

    def release_delayed_outcome_quarantine(self, outcome_id: str, *, released_by: str = "system", note: str = "") -> dict[str, Any]:
        released = self._delayed_outcome_bridge().release_quarantined(outcome_id=str(outcome_id), released_by=str(released_by), note=str(note or ""))
        return {"outcome_id": str(outcome_id), "released": bool(released), "status": "released" if released else "not_found", "released_by": str(released_by)}

    def retry_delayed_outcome_quarantine(self, outcome_id: str, *, retried_by: str = "system", planning_horizon: str | None = None, note: str = "") -> dict[str, Any]:
        retried = self._delayed_outcome_bridge().retry_quarantined(outcome_id=str(outcome_id), retried_by=str(retried_by), planning_horizon=planning_horizon, note=str(note or ""))
        return {"outcome_id": str(outcome_id), "retried": bool(retried), "status": "retried" if retried else "not_found", "retried_by": str(retried_by)}

    def get_governance_alignment(self, business_id: str) -> dict[str, Any]:
        service = build_business_autonomy_guarded_service(business_id=business_id, seed_admin_read_model=True)
        bridge = getattr(service, "_governance_alignment_bridge", None)
        if bridge is None:
            return {"business_id": business_id, "execution_verdict": {}, "normalized_request": {}}
        from application.business_autonomy.contracts import (
            BusinessExecutionRequest,
            BusinessGoalEnvelope,
            IntegrationMode,
        )
        request = BusinessExecutionRequest(
            envelope=BusinessGoalEnvelope(
                business_id=business_id,
                goal_id="alignment-preview",
                goal_type="alignment_preview",
                goal_payload={"estimated_cost": 0.0, "outbound_count": 0},
                metadata={"tenant_id": business_id, "autonomy_tier": "bounded_autonomy"},
            ),
            integration_mode=IntegrationMode.POLICY_GUARDED_DELEGATED,
            correlation_id="alignment-preview",
            idempotency_key="alignment-preview",
        )
        alignment = bridge.build_alignment(request=request, capability_allowed=True, policy_verdict={"allowed": True, "reason": "preview"})
        return {"business_id": business_id, "execution_verdict": dict(alignment.execution_verdict), "normalized_request": dict(alignment.normalized_request)}

    def get_registered_capabilities(self, business_id: str) -> dict[str, Any]:
        return get_registered_business_capabilities(
            business_id=business_id,
            service=self.stack.get("guarded_service"),
        )

    def get_trust_profile(self, business_id: str) -> dict[str, Any]:
        return get_business_trust_profile(
            business_id=business_id,
            service=self.stack.get("guarded_service"),
        )



def build_business_autonomy_route_handlers(*, stack: Mapping[str, Any] | None = None) -> BusinessAutonomyRouteHandlers:
    return BusinessAutonomyRouteHandlers(stack=stack or _default_stack())


__all__ = ["BusinessAutonomyRouteHandlers", "build_business_autonomy_route_handlers"]
