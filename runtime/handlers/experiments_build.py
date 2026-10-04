from __future__ import annotations

import hashlib
from collections.abc import Mapping

from runtime.experiments import (
    ACTION_CREATE_EXPERIMENT_V1,
    Experiment,
    ExperimentPlanBuilder,
    MetricDirection,
    VariantRole,
    build_experiment,
    build_experiments_service,
    validate_prefixed_id,
)

CANON_THIN_HANDLER = True


def handle_experiments_build(experiment_id: str, hypothesis: str, traffic_share: float) -> Experiment:
    return build_experiment(experiment_id=experiment_id, hypothesis=hypothesis, traffic_share=traffic_share)


def _required(payload: Mapping[str, object], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise ValueError(f"create_experiment requires {key}")
    return value


def _experiment_id(*, payload: Mapping[str, object], tenant_id: str, business_id: str, decision_id: str) -> str:
    supplied = str(payload.get("experiment_id") or "").strip()
    if supplied:
        return validate_prefixed_id(supplied, "exp")
    digest = hashlib.sha256(f"{tenant_id}:{business_id}:{decision_id}".encode("utf-8")).hexdigest()[:32]
    return f"exp_{digest}"


def _variants(payload: Mapping[str, object]):
    if "variants" not in payload:
        return [("control", VariantRole.CONTROL, 0.5), ("treatment", VariantRole.TREATMENT, 0.5)]
    raw = payload["variants"]
    if not isinstance(raw, list):
        raise ValueError("create_experiment variants must be a list")
    out = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise ValueError("create_experiment variant must be an object")
        out.append(
            (_required(item, "name"), VariantRole(_required(item, "role")), float(item.get("traffic_share")))
        )
    return out


def _metrics(payload: Mapping[str, object]):
    if "metrics" not in payload:
        key = str(payload.get("primary_metric") or "").strip()
        if not key:
            raise ValueError("create_experiment requires metrics or primary_metric")
        return [(key, MetricDirection.INCREASE, 0.0, False)]
    raw = payload["metrics"]
    if not isinstance(raw, list):
        raise ValueError("create_experiment metrics must be a list")
    out = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise ValueError("create_experiment metric must be an object")
        out.append((
            _required(item, "metric_key"),
            MetricDirection(str(item.get("direction") or "increase").strip()),
            float(item.get("minimum_detectable_effect") or 0.0),
            bool(item.get("guardrail", False)),
        ))
    return out


def handle_create_experiment(payload: dict, effects, env, *, event_store):
    del effects
    if env is None or getattr(env, "decision", None) is None:
        raise RuntimeError("CREATE_EXPERIMENT_DECISION_ENVELOPE_REQUIRED")
    decision = env.decision
    if str(getattr(decision, "action", "") or "") != ACTION_CREATE_EXPERIMENT_V1:
        raise RuntimeError("CREATE_EXPERIMENT_ACTION_MISMATCH")
    body = dict(payload or {})
    tenant_id = _required(body, "tenant_id")
    business_id = _required(body, "business_id")
    contract_value = getattr(decision, "contract_v2", None)
    contract = dict(contract_value) if isinstance(contract_value, Mapping) else {}
    contract_business_id = str(contract.get("business_id") or "").strip()
    if contract_business_id and contract_business_id != business_id:
        raise PermissionError("CREATE_EXPERIMENT_BUSINESS_ID_MISMATCH")
    decision_id = str(getattr(decision, "decision_id", "") or "").strip()
    if not decision_id:
        raise RuntimeError("CREATE_EXPERIMENT_DECISION_ID_REQUIRED")
    correlation_id = str(getattr(decision, "correlation_id", "") or "").strip()
    metadata = {str(k): str(v) for k, v in dict(body.get("metadata") or {}).items()}
    metadata.update(
        decision_id=decision_id,
        correlation_id=correlation_id,
        launch_path="RuntimeExecutor",
        policy_governed="true",
    )
    plan = ExperimentPlanBuilder().build(
        experiment_id=_experiment_id(
            payload=body, tenant_id=tenant_id, business_id=business_id, decision_id=decision_id
        ),
        name=_required(body, "name"),
        hypothesis=_required(body, "hypothesis"),
        subject_key=str(body["subject_key"]).strip() if "subject_key" in body else "customer",
        audience_key=str(body["audience_key"]).strip() if "audience_key" in body else "all",
        owner=str(body["owner"]).strip()
        if "owner" in body
        else str(getattr(decision, "issuer_id", "") or "system").strip(),
        variant_definitions=_variants(body),
        metric_definitions=_metrics(body),
        minimum_sample_size=int(body["minimum_sample_size"]) if "minimum_sample_size" in body else 100,
        duration_days=int(body["duration_days"]) if "duration_days" in body else 14,
        overlap_keys=[str(item) for item in body.get("overlap_keys", [])],
        metadata=metadata,
    )
    service = build_experiments_service(
        event_store=event_store, tenant_id=tenant_id, business_id=business_id
    )
    active = service.register_experiment(plan)
    return {
        "ok": True,
        "status": "verified",
        "experiment_id": active.experiment_id,
        "experiment_status": active.status.value,
        "hypothesis": active.hypothesis,
        "duration_days": active.duration_days,
        "decision_id": decision_id,
        "correlation_id": correlation_id,
        "policy_governed": True,
    }


__all__ = [
    "handle_create_experiment",
    "handle_experiments_build",
]
