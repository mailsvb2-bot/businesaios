from __future__ import annotations

from dataclasses import replace
from typing import Any

from execution.business_operating_memory import (
    project_business_memory_contract_bundle,
    project_business_memory_meta_payloads,
)
from execution.headless_trace import HeadlessTrace

CANON_AUTONOMY_STATE_ASSEMBLY = True


class AutonomyStateAssembly:
    def __init__(self, *, contract: Any) -> None:
        self._contract = contract

    def load_goal_plan_context(self, *, request: Any, trace: HeadlessTrace | None = None) -> dict[str, Any]:
        if self._contract._goal_plan_memory_service is None:
            return {}
        try:
            return dict(
                self._contract._goal_plan_memory_service.load_context(
                    tenant_id=request.tenant_id,
                    business_id=request.business_id,
                    goal=request.goal,
                )
                or {}
            )
        except Exception as exc:
            if trace is not None:
                trace.record(
                    event_type="goal_plan_load_failed",
                    step_index=0,
                    payload={"error": type(exc).__name__, "message": str(exc)},
                )
            return {}

    def load_performance_context(self, *, request: Any, trace: HeadlessTrace | None = None) -> dict[str, Any]:
        service = getattr(self._contract, "_performance_feedback_learning_service", None)
        if service is None:
            return {}
        try:
            return dict(
                service.load_context(
                    tenant_id=request.tenant_id,
                    business_id=request.business_id,
                    goal=request.goal,
                )
                or {}
            )
        except Exception as exc:
            if trace is not None:
                trace.record(
                    event_type="performance_context_load_failed",
                    step_index=0,
                    payload={"error": type(exc).__name__, "message": str(exc)},
                )
            return {}

    def load_adaptive_optimization_context(self, *, request: Any, trace: HeadlessTrace | None = None) -> dict[str, Any]:
        service = getattr(self._contract, "_adaptive_optimization_service", None)
        if service is None:
            return {}
        runtime_capabilities = dict((request.meta or {}).get("runtime_capabilities") or {})
        capability_key = str((request.meta or {}).get("preferred_action_type") or (next(iter(runtime_capabilities.keys()), "")) or "")
        if not capability_key:
            return {}
        try:
            return dict(service.load_context(tenant_id=request.tenant_id, business_id=request.business_id, capability_key=capability_key) or {})
        except Exception as exc:
            if trace is not None:
                trace.record(event_type="adaptive_optimization_context_load_failed", step_index=0, payload={"error": type(exc).__name__, "message": str(exc), "capability_key": capability_key})
            return {}

    def load_multi_goal_context(self, *, request: Any, trace: HeadlessTrace | None = None) -> dict[str, Any]:
        service = getattr(self._contract, "_multi_goal_planner_service", None)
        if service is None:
            return {}
        try:
            return dict(
                service.load_context(tenant_id=request.tenant_id, business_id=request.business_id) or {}
            )
        except Exception as exc:
            if trace is not None:
                trace.record(
                    event_type="multi_goal_context_load_failed",
                    step_index=0,
                    payload={"error": type(exc).__name__, "message": str(exc)},
                )
            return {}


    def load_owner_path_context(self, *, request: Any, trace: HeadlessTrace | None = None) -> dict[str, Any]:
        service = getattr(self._contract, "_owner_path_service", None)
        if service is None:
            return {}
        try:
            return dict(service.load_context(tenant_id=request.tenant_id, business_id=request.business_id) or {})
        except Exception as exc:
            if trace is not None:
                trace.record(
                    event_type="owner_path_context_load_failed",
                    step_index=0,
                    payload={"error": type(exc).__name__, "message": str(exc)},
                )
            return {}

    def load_business_memory_context(self, *, request: Any, trace: HeadlessTrace | None = None) -> dict[str, Any]:
        if self._contract._business_memory_service is None:
            return {}
        try:
            return dict(
                self._contract._business_memory_service.get(
                    business_id=request.business_id,
                    tenant_id=request.tenant_id,
                    request_profile=dict(request.profile or {}),
                )
                or {}
            )
        except Exception as exc:
            if trace is not None:
                trace.record(
                    event_type="business_memory_load_failed",
                    step_index=0,
                    payload={"error": type(exc).__name__, "message": str(exc)},
                )
            return {}

    @staticmethod
    def enrich_request_with_business_memory(*, request: Any, business_memory_context: dict[str, Any]) -> Any:
        bundle = project_business_memory_contract_bundle(dict(business_memory_context or {}))
        meta_payloads = project_business_memory_meta_payloads(dict(business_memory_context or {}))
        memory_profile = dict(bundle.get("profile") or {})
        profile = {**memory_profile, **dict(request.profile or {})}
        meta = dict(request.meta or {})
        meta.update(meta_payloads)
        meta.setdefault("autonomy_tier", request.autonomy_tier)
        meta.setdefault("approval_policy", dict(request.approval_policy or {}))
        return replace(request, profile=profile, meta=meta)

    @staticmethod
    def enrich_request_with_goal_plan(*, request: Any, goal_plan_context: dict[str, Any]) -> Any:
        meta = dict(request.meta or {})
        meta["goal_plan"] = dict(goal_plan_context or {})
        return replace(request, meta=meta)

    @staticmethod
    def enrich_request_with_performance_context(*, request: Any, performance_context: dict[str, Any]) -> Any:
        meta = dict(request.meta or {})
        meta["performance_learning"] = dict(performance_context or {})
        return replace(request, meta=meta)

    @staticmethod
    def enrich_request_with_adaptive_optimization_context(*, request: Any, adaptive_optimization_context: dict[str, Any]) -> Any:
        meta = dict(request.meta or {})
        meta["adaptive_optimization"] = dict(adaptive_optimization_context or {})
        return replace(request, meta=meta)

    @staticmethod
    def enrich_request_with_multi_goal_context(*, request: Any, multi_goal_context: dict[str, Any]) -> Any:
        meta = dict(request.meta or {})
        meta["multi_goal"] = dict(multi_goal_context or {})
        return replace(request, meta=meta)

    @staticmethod
    def enrich_request_with_owner_path_context(*, request: Any, owner_path_context: dict[str, Any]) -> Any:
        meta = dict(request.meta or {})
        meta["owner_path"] = dict(owner_path_context or {})
        return replace(request, meta=meta)

    @staticmethod
    def enrich_request_with_previous_feedback(*, request: Any, previous_feedback: dict[str, Any]) -> Any:
        meta = dict(request.meta or {})
        meta["previous_feedback"] = dict(previous_feedback or {})
        return replace(request, meta=meta)

    def build_runtime_request(
        self,
        *,
        request: Any,
        previous_feedback: dict[str, Any],
        business_memory_context: dict[str, Any],
        goal_plan_context: dict[str, Any],
        performance_context: dict[str, Any],
        adaptive_optimization_context: dict[str, Any],
        multi_goal_context: dict[str, Any],
        owner_path_context: dict[str, Any],
    ) -> Any:
        runtime_request = self.enrich_request_with_business_memory(
            request=request,
            business_memory_context=business_memory_context,
        )
        runtime_request = self.enrich_request_with_goal_plan(
            request=runtime_request,
            goal_plan_context=goal_plan_context,
        )
        runtime_request = self.enrich_request_with_performance_context(
            request=runtime_request,
            performance_context=performance_context,
        )
        runtime_request = self.enrich_request_with_adaptive_optimization_context(
            request=runtime_request,
            adaptive_optimization_context=adaptive_optimization_context,
        )
        runtime_request = self.enrich_request_with_multi_goal_context(
            request=runtime_request,
            multi_goal_context=multi_goal_context,
        )
        runtime_request = self.enrich_request_with_owner_path_context(
            request=runtime_request,
            owner_path_context=owner_path_context,
        )
        return self.enrich_request_with_previous_feedback(
            request=runtime_request,
            previous_feedback=previous_feedback,
        )

    def assemble_state(
        self,
        *,
        request: Any,
        trace: HeadlessTrace,
        step_index: int,
        previous_feedback: dict[str, Any],
        business_memory_context: dict[str, Any],
    ) -> Any:
        state = self._contract._state_mapper.to_world_state(
            request=request,
            step_index=step_index,
            previous_feedback=previous_feedback,
        )
        capability_health_registry = getattr(self._contract, "_capability_health_registry", None)
        capability_health_service = getattr(self._contract, "_capability_health_scoring_service", None)
        existing_runtime = dict(dict(getattr(state, "meta", {}) or {}).get("runtime_capabilities") or {})
        if existing_runtime:
            if capability_health_registry is not None:
                runtime_snapshot = capability_health_registry.runtime_capabilities_for_actions(
                    tenant_id=request.tenant_id,
                    action_types=[str(key) for key in existing_runtime.keys()],
                    existing_runtime_capabilities=existing_runtime,
                )
            elif capability_health_service is not None:
                load_for_actions = getattr(capability_health_service, "load_runtime_snapshot_for_actions", None)
                if callable(load_for_actions):
                    runtime_snapshot = load_for_actions(
                        tenant_id=request.tenant_id,
                        action_types=[str(key) for key in existing_runtime.keys()],
                    )
                    runtime_snapshot = {
                        str(key): {**dict(runtime_snapshot.get(str(key)) or {}), **dict(existing_runtime.get(str(key)) or {})}
                        for key in set(existing_runtime.keys()) | set(runtime_snapshot.keys())
                    }
                else:
                    capability_keys = [str(key) for key in existing_runtime.keys()]
                    raw_runtime_snapshot = capability_health_service.load_runtime_snapshot(
                        tenant_id=request.tenant_id,
                        capability_keys=capability_keys,
                    )
                    runtime_snapshot = {
                        str(key): {**dict(raw_runtime_snapshot.get(str(key)) or {}), **dict(existing_runtime.get(str(key)) or {})}
                        for key in set(existing_runtime.keys()) | set(raw_runtime_snapshot.keys())
                    }
            else:
                runtime_snapshot = existing_runtime
            meta = dict(getattr(state, "meta", {}) or {})
            meta["runtime_capabilities"] = runtime_snapshot
            state = replace(state, meta=meta)
        adapter = getattr(self._contract, "_business_memory_state_adapter", None)
        if adapter is not None:
            inject_context = getattr(adapter, "inject_context", None)
            if callable(inject_context):
                state = inject_context(
                    world_state=state,
                    memory_context=dict(business_memory_context or {}),
                )
            else:
                state = adapter.inject(
                    world_state=state,
                    tenant_id=request.tenant_id,
                    business_id=request.business_id,
                )
        goal_plan_context = dict(request.meta.get("goal_plan") or {})
        if goal_plan_context:
            meta = dict(getattr(state, "meta", {}) or {})
            meta["goal_plan_context"] = {
                **goal_plan_context,
                "evidence_only": True,
                "must_not_issue_decision": True,
            }
            state = replace(state, meta=meta)
        performance_context = dict(request.meta.get("performance_learning") or {})
        if performance_context:
            meta = dict(getattr(state, "meta", {}) or {})
            meta["performance_learning"] = {**performance_context, "evidence_only": True, "must_not_issue_decision": True}
            state = replace(state, meta=meta)
        adaptive_optimization_context = dict(request.meta.get("adaptive_optimization") or {})
        if adaptive_optimization_context:
            meta = dict(getattr(state, "meta", {}) or {})
            meta["adaptive_optimization"] = {**adaptive_optimization_context, "evidence_only": True, "must_not_issue_decision": True}
            state = replace(state, meta=meta)
        owner_path_context = dict(request.meta.get("owner_path") or {})
        if owner_path_context:
            meta = dict(getattr(state, "meta", {}) or {})
            meta["owner_path"] = {**owner_path_context, "evidence_only": True, "must_not_issue_decision": True}
            state = replace(state, meta=meta)
        multi_goal_context = dict(request.meta.get("multi_goal") or {})
        if multi_goal_context:
            meta = dict(getattr(state, "meta", {}) or {})
            meta["multi_goal_context"] = {**multi_goal_context, "evidence_only": True, "must_not_issue_decision": True}
            state = replace(state, meta=meta)
        if self._contract._state_store is not None:
            self._contract._state_store.save_snapshot(
                run_id=trace.run_id,
                step_index=step_index,
                phase="state_mapped",
                snapshot={
                    "tenant_id": request.tenant_id,
                    "business_id": request.business_id,
                    "goal": request.goal,
                    "meta": dict(getattr(state, "meta", {}) or {}),
                    "business_memory": dict(project_business_memory_contract_bundle(dict(business_memory_context or {})).get("evidence") or {}),
                    "business_memory_summary": dict(project_business_memory_contract_bundle(dict(business_memory_context or {})).get("governance_summary") or {}),
                    "goal_plan": dict(goal_plan_context),
                    "performance_learning": dict(request.meta.get("performance_learning") or {}),
                    "adaptive_optimization": dict(request.meta.get("adaptive_optimization") or {}),
                    "multi_goal": dict(request.meta.get("multi_goal") or {}),
                    "owner_path": dict(request.meta.get("owner_path") or {}),
                },
            )
        trace.record(
            event_type="state_mapped",
            step_index=step_index,
            payload={
                "tenant_id": request.tenant_id,
                "business_id": request.business_id,
                "goal": request.goal,
            },
        )
        return state


__all__ = ["CANON_AUTONOMY_STATE_ASSEMBLY", "AutonomyStateAssembly"]
