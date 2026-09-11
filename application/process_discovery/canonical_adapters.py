from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from application.business_autonomy.provider_catalog import MESSAGING_GUARDED_WRITE_PROVIDER_KEYS
from application.business_autonomy.provider_delivery_truth import provider_approval_completion_truth
from shared.types import new_id

from .contracts import (
    AgentBlueprint,
    AutonomyStage,
    ComparisonEvidence,
    InterventionProof,
    InterventionSpend,
    MoneyStatus,
    ProcessBaseline,
    ProcessObservation,
)
from .ports import BlueprintLedger, TrustedMeasurementSource, TrustedProcessEvidenceSource

PROCESS_OBSERVATION_EVENT = "business.process.observation.v1"
PROCESS_BLUEPRINT_EVENT = "business.process.blueprint.v1"
PROCESS_DECISION_BINDING_EVENT = "business.process.decision_binding.v1"


def _dt(value: object) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("timestamp_required")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp_timezone_required")
    return parsed.astimezone(UTC)


def _optional_int(value: object) -> int | None:
    if value in {None, ""}:
        return None
    return int(value)


def _observation_payload(item: ProcessObservation) -> dict[str, Any]:
    return {
        "tenant_id": item.tenant_id, "business_id": item.business_id, "process_key": item.process_key,
        "occurred_at": item.occurred_at.isoformat(), "source": item.source, "evidence_id": item.evidence_id,
        "manual_minutes": item.manual_minutes, "actor_cost_per_hour_minor": item.actor_cost_per_hour_minor,
        "direct_loss_minor": item.direct_loss_minor, "revenue_at_risk_minor": item.revenue_at_risk_minor,
        "currency": item.currency, "automation_fit": item.automation_fit,
        "operational_risk": item.operational_risk, "trust_weight": item.trust_weight,
        "metadata": dict(item.metadata),
    }


def _observation_from_payload(payload: Mapping[str, Any]) -> ProcessObservation:
    return ProcessObservation(
        tenant_id=str(payload.get("tenant_id") or ""), business_id=str(payload.get("business_id") or ""),
        process_key=str(payload.get("process_key") or ""), occurred_at=_dt(payload.get("occurred_at")),
        source=str(payload.get("source") or ""), evidence_id=str(payload.get("evidence_id") or ""),
        manual_minutes=int(payload.get("manual_minutes") or 0),
        actor_cost_per_hour_minor=_optional_int(payload.get("actor_cost_per_hour_minor")),
        direct_loss_minor=_optional_int(payload.get("direct_loss_minor")),
        revenue_at_risk_minor=_optional_int(payload.get("revenue_at_risk_minor")),
        currency=str(payload.get("currency") or "").strip() or None,
        automation_fit=float(payload.get("automation_fit") or 0.0),
        operational_risk=float(payload.get("operational_risk") or 0.0),
        trust_weight=float(payload.get("trust_weight") if payload.get("trust_weight") is not None else 1.0),
        metadata=dict(payload.get("metadata") or {}),
    )


def _baseline_payload(item: ProcessBaseline) -> dict[str, Any]:
    data = asdict(item)
    data["window_start"], data["window_end"] = item.window_start.isoformat(), item.window_end.isoformat()
    data["money_status"] = item.money_status.value
    data["evidence_refs"] = list(item.evidence_refs)
    return data


def _baseline_from_payload(payload: Mapping[str, Any]) -> ProcessBaseline:
    return ProcessBaseline(
        tenant_id=str(payload["tenant_id"]), business_id=str(payload["business_id"]), process_key=str(payload["process_key"]),
        window_start=_dt(payload["window_start"]), window_end=_dt(payload["window_end"]),
        window_days=int(payload["window_days"]), observation_count=int(payload["observation_count"]),
        source_count=int(payload["source_count"]), occurrences_per_30d=float(payload["occurrences_per_30d"]),
        manual_minutes_per_30d=int(payload["manual_minutes_per_30d"]),
        realized_loss_minor_per_30d=_optional_int(payload.get("realized_loss_minor_per_30d")),
        revenue_at_risk_minor_per_30d=_optional_int(payload.get("revenue_at_risk_minor_per_30d")),
        currency=str(payload.get("currency") or "").strip() or None, money_status=MoneyStatus(str(payload["money_status"])),
        average_automation_fit=float(payload["average_automation_fit"]), average_operational_risk=float(payload["average_operational_risk"]),
        confidence=float(payload["confidence"]), evidence_refs=tuple(payload.get("evidence_refs") or ()),
        evidence_fingerprint=str(payload.get("evidence_fingerprint") or ""),
    )


def _blueprint_payload(item: AgentBlueprint) -> dict[str, Any]:
    return {
        "blueprint_id": item.blueprint_id, "tenant_id": item.tenant_id, "business_id": item.business_id,
        "process_key": item.process_key, "opportunity_id": item.opportunity_id,
        "baseline_fingerprint": item.baseline_fingerprint, "built_at": item.built_at.isoformat(),
        "owner_goal": item.owner_goal, "initial_stage": item.initial_stage.value,
        "promotion_path": [stage.value for stage in item.promotion_path],
        "requested_capabilities": list(item.requested_capabilities), "forbidden_side_effects": list(item.forbidden_side_effects),
        "expected_coverage": item.expected_coverage, "setup_cost_minor": item.setup_cost_minor,
        "currency": item.currency, "success_metrics": list(item.success_metrics),
        "rollback_conditions": list(item.rollback_conditions), "executable": item.executable,
        "metadata": dict(item.metadata),
    }


def _blueprint_from_payload(payload: Mapping[str, Any]) -> AgentBlueprint:
    return AgentBlueprint(
        blueprint_id=str(payload["blueprint_id"]), tenant_id=str(payload["tenant_id"]),
        business_id=str(payload["business_id"]), process_key=str(payload["process_key"]),
        opportunity_id=str(payload["opportunity_id"]), baseline_fingerprint=str(payload["baseline_fingerprint"]),
        built_at=_dt(payload["built_at"]), owner_goal=str(payload["owner_goal"]),
        initial_stage=AutonomyStage(str(payload["initial_stage"])),
        promotion_path=tuple(AutonomyStage(str(value)) for value in payload.get("promotion_path") or ()),
        requested_capabilities=tuple(payload.get("requested_capabilities") or ()),
        forbidden_side_effects=tuple(payload.get("forbidden_side_effects") or ()),
        expected_coverage=float(payload["expected_coverage"]), setup_cost_minor=_optional_int(payload.get("setup_cost_minor")),
        currency=str(payload.get("currency") or "").strip() or None, success_metrics=tuple(payload.get("success_metrics") or ()),
        rollback_conditions=tuple(payload.get("rollback_conditions") or ()), executable=bool(payload.get("executable")),
        metadata=dict(payload.get("metadata") or {}),
    )


@dataclass
class CanonicalProcessEvidenceStore(TrustedProcessEvidenceSource):
    event_store: Any

    def record_owner_observation(self, *, tenant_id: str, business_id: str, user_id: str | None, payload: Mapping[str, Any], request_id: str | None = None) -> ProcessObservation:
        occurred_at = _dt(payload.get("occurred_at"))
        if occurred_at > datetime.now(UTC) + timedelta(minutes=5):
            raise ValueError("occurred_at_in_future")
        request_text = str(request_id or "").strip()
        evidence_id = (
            f"pev_{hashlib.sha256(f'{tenant_id}\x1f{business_id}\x1f{request_text}'.encode()).hexdigest()[:20]}"
            if request_text else new_id("pev")
        )
        item = ProcessObservation(
            tenant_id=tenant_id, business_id=business_id, process_key=str(payload.get("process_key") or "").strip(),
            occurred_at=occurred_at, source="owner_asserted", evidence_id=evidence_id,
            manual_minutes=int(payload.get("manual_minutes") or 0),
            actor_cost_per_hour_minor=_optional_int(payload.get("actor_cost_per_hour_minor")),
            direct_loss_minor=_optional_int(payload.get("direct_loss_minor")),
            revenue_at_risk_minor=_optional_int(payload.get("revenue_at_risk_minor")),
            currency=str(payload.get("currency") or "").strip() or None,
            automation_fit=float(payload.get("automation_fit") if payload.get("automation_fit") is not None else 0.5),
            operational_risk=float(payload.get("operational_risk") if payload.get("operational_risk") is not None else 0.5),
            trust_weight=0.65, metadata={"assertion_kind": "owner_process_occurrence", "server_issued_evidence_id": True},
        )
        self.event_store.append(tenant_id=tenant_id, user_id=user_id, event_type=PROCESS_OBSERVATION_EVENT, payload=_observation_payload(item))
        return item

    def load_process_observations(self, *, tenant_id: str, business_id: str) -> Sequence[ProcessObservation]:
        rows = self.event_store.latest_events(tenant_id=tenant_id, event_type=PROCESS_OBSERVATION_EVENT, limit=5000)
        items = []
        for row in reversed(list(rows)):
            payload = dict(row.get("payload") or {})
            if str(payload.get("business_id") or "") != business_id:
                continue
            items.append(_observation_from_payload(payload))
        return tuple(items)


@dataclass
class CanonicalBlueprintLedger(BlueprintLedger):
    event_store: Any

    def save(self, *, blueprint: AgentBlueprint, baseline: ProcessBaseline) -> None:
        existing = self.get(tenant_id=blueprint.tenant_id, business_id=blueprint.business_id, blueprint_id=blueprint.blueprint_id)
        new_payload = {"business_id": blueprint.business_id, "blueprint": _blueprint_payload(blueprint), "baseline": _baseline_payload(baseline)}
        if existing is not None:
            old_payload = {"business_id": existing[0].business_id, "blueprint": _blueprint_payload(existing[0]), "baseline": _baseline_payload(existing[1])}
            if json.dumps(old_payload, sort_keys=True) != json.dumps(new_payload, sort_keys=True):
                raise ValueError("blueprint_id_conflict")
            return
        self.event_store.append(tenant_id=blueprint.tenant_id, user_id=None, event_type=PROCESS_BLUEPRINT_EVENT, payload=new_payload)

    def get(self, *, tenant_id: str, business_id: str, blueprint_id: str) -> tuple[AgentBlueprint, ProcessBaseline] | None:
        rows = self.event_store.latest_events(tenant_id=tenant_id, event_type=PROCESS_BLUEPRINT_EVENT, limit=2000)
        for row in rows:
            payload = dict(row.get("payload") or {})
            bp = dict(payload.get("blueprint") or {})
            if str(payload.get("business_id") or "") != business_id or str(bp.get("blueprint_id") or "") != blueprint_id:
                continue
            return _blueprint_from_payload(bp), _baseline_from_payload(dict(payload.get("baseline") or {}))
        return None


ProviderHistoryReader = Callable[..., Sequence[Mapping[str, Any]]]


@dataclass
class CanonicalProcessMeasurementSource(TrustedMeasurementSource):
    event_store: Any
    evidence_source: CanonicalProcessEvidenceStore
    provider_history_reader: ProviderHistoryReader | None = None

    def record_decision_result(self, *, tenant_id: str, business_id: str, blueprint: AgentBlueprint, result: Mapping[str, Any]) -> dict[str, Any]:
        steps = []
        for item in result.get("steps") or []:
            row = dict(item or {})
            steps.append({key: row.get(key) for key in ("step_index", "decision_id", "action_id", "action", "status", "attempted", "executed", "verified", "operator_required", "reason")})
        payload = {
            "business_id": business_id, "blueprint_id": blueprint.blueprint_id,
            "baseline_fingerprint": blueprint.baseline_fingerprint, "run_id": str(result.get("run_id") or ""),
            "trace_id": str(result.get("trace_id") or ""), "completed": bool(result.get("completed")),
            "stop_reason": str(result.get("stop_reason") or ""), "steps": steps,
        }
        if not payload["run_id"]:
            raise ValueError("decision_run_id_missing")
        self.event_store.append(tenant_id=tenant_id, user_id=None, event_type=PROCESS_DECISION_BINDING_EVENT, payload=payload)
        return payload

    def _bindings(self, *, tenant_id: str, business_id: str, blueprint_id: str) -> list[dict[str, Any]]:
        rows = self.event_store.latest_events(tenant_id=tenant_id, event_type=PROCESS_DECISION_BINDING_EVENT, limit=1000)
        out = []
        for row in rows:
            payload = dict(row.get("payload") or {})
            if str(payload.get("business_id") or "") == business_id and str(payload.get("blueprint_id") or "") == blueprint_id:
                out.append({"event_id": str(row.get("event_id") or ""), "ts_iso": str(row.get("ts_iso") or ""), **payload})
        return out

    def load_intervention_proof(self, *, tenant_id: str, business_id: str, blueprint: AgentBlueprint) -> InterventionProof | None:
        for binding in self._bindings(tenant_id=tenant_id, business_id=business_id, blueprint_id=blueprint.blueprint_id):
            for step in binding.get("steps") or []:
                if bool(step.get("executed")) and bool(step.get("verified")):
                    return InterventionProof(
                        tenant_id=tenant_id, business_id=business_id, blueprint_id=blueprint.blueprint_id,
                        intervention_id=f"decision:{binding['run_id']}:{step.get('action_id') or step.get('decision_id')}",
                        started_at=_dt(binding["ts_iso"]), server_validated=True, execution_verified=True,
                        run_id=str(binding.get("run_id") or "") or None, decision_id=str(step.get("decision_id") or "") or None,
                        action_id=str(step.get("action_id") or "") or None,
                        evidence_refs=tuple(value for value in (binding.get("event_id"), step.get("action_id")) if value),
                    )
            provider = self._provider_delivery_proof(tenant_id=tenant_id, business_id=business_id, binding=binding)
            if provider is not None:
                return InterventionProof(tenant_id=tenant_id, business_id=business_id, blueprint_id=blueprint.blueprint_id, **provider)
        return None

    def _provider_delivery_proof(self, *, tenant_id: str, business_id: str, binding: Mapping[str, Any]) -> dict[str, Any] | None:
        if self.provider_history_reader is None:
            return None
        identities = {(str(binding.get("run_id") or ""), str(step.get("decision_id") or ""), str(step.get("action_id") or "")) for step in binding.get("steps") or []}
        for provider_key in sorted(MESSAGING_GUARDED_WRITE_PROVIDER_KEYS):
            for row in self.provider_history_reader(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key, limit=100):
                provenance = dict(row.get("decision_provenance") or {})
                identity = (str(provenance.get("run_id") or ""), str(provenance.get("decision_id") or ""), str(provenance.get("action_id") or ""))
                if identity not in identities:
                    continue
                delivered, _, _ = provider_approval_completion_truth(provider_key=provider_key, result=row)
                if not delivered:
                    continue
                parsed = dict(row.get("parsed_response") or {})
                queue_job_id = str(row.get("queue_job_id") or "")
                resource_id = str(parsed.get("resource_id") or "")
                return {
                    "intervention_id": f"provider:{provider_key}:{queue_job_id or resource_id}",
                    "started_at": _dt(row.get("recorded_at_utc") or binding.get("ts_iso")),
                    "server_validated": True, "execution_verified": True,
                    "run_id": identity[0] or None, "decision_id": identity[1] or None, "action_id": identity[2] or None,
                    "evidence_refs": tuple(value for value in (binding.get("event_id"), queue_job_id, resource_id) if value),
                }
        return None

    def load_after_observations(self, *, tenant_id: str, business_id: str, blueprint: AgentBlueprint, intervention: InterventionProof) -> Sequence[ProcessObservation]:
        return tuple(item for item in self.evidence_source.load_process_observations(tenant_id=tenant_id, business_id=business_id) if item.process_key == blueprint.process_key and item.occurred_at >= intervention.started_at)

    def load_intervention_spend(self, *, tenant_id: str, business_id: str, blueprint: AgentBlueprint, intervention: InterventionProof) -> InterventionSpend:
        if blueprint.setup_cost_minor is None:
            return InterventionSpend()
        return InterventionSpend(setup_cost_minor=blueprint.setup_cost_minor, currency=blueprint.currency)

    def load_comparison_evidence(self, *, tenant_id: str, business_id: str, blueprint: AgentBlueprint, intervention: InterventionProof) -> ComparisonEvidence:
        return ComparisonEvidence()


__all__ = [
    "CanonicalBlueprintLedger", "CanonicalProcessEvidenceStore", "CanonicalProcessMeasurementSource",
    "PROCESS_BLUEPRINT_EVENT", "PROCESS_DECISION_BINDING_EVENT", "PROCESS_OBSERVATION_EVENT",
]
