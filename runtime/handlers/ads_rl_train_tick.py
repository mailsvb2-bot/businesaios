from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping
from typing import Any

from core.events.event_types import ADS_RL_TRAIN_COMPLETED
from core.events.log import EventLog
from execution.verification.evidence_types import evidence_status_is_positive
from runtime.ads import (
    DatasetBuilder,
    OPEGate,
    RewardComputer,
    RewardWindow,
    RLTrainer,
    bind_runtime_state,
    maturity_gate,
    policy_store,
)
from runtime.governance import ProfitMetricsService
from runtime.ports.effects import EffectsPort
from runtime.tenancy import as_tenant_id

CANON_THIN_HANDLER = True

logger = logging.getLogger(__name__)

ACTION_NAME = "ads_rl_train_tick@v1"
_COMPLETION_NAMESPACE = uuid.UUID("5c7f3498-d352-4385-bfc5-424e90df54f5")


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = str(payload.get(field) or "").strip()
    if not value:
        raise RuntimeError(f"{field.upper()}_REQUIRED")
    return value


def _delivery_evidence(delivery: object) -> dict[str, Any] | None:
    if not isinstance(delivery, Mapping):
        return None
    for key in ("router_evidence", "evidence", "verification"):
        candidate = delivery.get(key)
        if isinstance(candidate, Mapping) and str(candidate.get("source") or "").strip():
            return dict(candidate)
    return None


def _proof_is_positive(proof: Mapping[str, Any] | None) -> bool:
    if not isinstance(proof, Mapping) or proof.get("verified") is False:
        return False
    return evidence_status_is_positive(proof.get("status")) or proof.get("verified") is True


def _send(
    *,
    effects: EffectsPort,
    body: Mapping[str, Any],
    tenant_id: str,
    user_id: str,
    decision_id: str,
    correlation_id: str,
    text: str,
    track_event_type: str,
    track_payload: dict[str, Any],
):
    payload = dict(track_payload)
    payload.setdefault("tenant_id", tenant_id)
    return effects.send_message(
        decision_id=decision_id,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        user_id=user_id,
        text=text,
        track_event_type=track_event_type,
        track_payload=payload,
        channel=str(body.get("channel") or "telegram"),
        channel_policy=(
            dict(body.get("channel_policy") or {})
            if isinstance(body.get("channel_policy"), Mapping)
            else None
        ),
        critical=False,
    )


def _skipped_outcome(
    *,
    delivery: Any,
    reason: str,
    report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "skipped",
        "reason": str(reason),
        "report": dict(report or {}),
        "delivery": delivery,
        "router_evidence": None,
    }


def _report_payload(report: Any) -> dict[str, Any]:
    if isinstance(report, Mapping):
        source = report
        read = source.get
    else:
        read = lambda key, default=None: getattr(report, key, default)
    return {
        "ok": bool(read("ok", False)),
        "reason": str(read("reason", "")),
        "n": int(read("n", 0) or 0),
        "policy_version": read("policy_version"),
        "ope_reason": read("ope_reason"),
        "avg_reward_minor": read("avg_reward_minor"),
    }


def _completion_event_id(*, tenant_id: str, decision_id: str) -> str:
    return str(
        uuid.uuid5(
            _COMPLETION_NAMESPACE,
            f"businesaios:ads-rl-train:{tenant_id}:{decision_id}",
        )
    )


def _load_completion(
    *,
    event_store: Any,
    tenant_id: str,
    decision_id: str,
) -> tuple[dict[str, Any], str] | None:
    events = EventLog(event_store, tenant=str(tenant_id)).get_events(
        str(decision_id),
        ADS_RL_TRAIN_COMPLETED,
    )
    for event in reversed(events):
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        report = payload.get("report")
        if int(payload.get("schema_version") or 0) != 1 or not isinstance(report, dict):
            continue
        event_id = str(event.get("event_id") or "").strip()
        if event_id and bool(report.get("ok")):
            return dict(report), event_id
    return None


def _persist_completion(
    *,
    event_store: Any,
    tenant_id: str,
    user_id: str,
    decision_id: str,
    correlation_id: str,
    report: dict[str, Any],
) -> str:
    event_id = _completion_event_id(
        tenant_id=tenant_id,
        decision_id=decision_id,
    )
    log = EventLog(event_store, tenant=str(tenant_id))
    payload = {
        "schema_version": 1,
        "tenant_id": str(tenant_id),
        "report": dict(report),
    }
    try:
        log.emit(
            event_id=event_id,
            event_type=ADS_RL_TRAIN_COMPLETED,
            source="ads_rl",
            user_id=str(user_id),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload=payload,
        )
    except Exception:
        raced = _load_completion(
            event_store=event_store,
            tenant_id=tenant_id,
            decision_id=decision_id,
        )
        if raced is None or raced[0] != report:
            raise
        return raced[1]
    return event_id


def _completion_evidence(
    *,
    event_id: str,
    tenant_id: str,
    report: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "source": "ledger",
        "verified": True,
        "status": "verified",
        "code": "ads_rl_training_recorded",
        "external_refs": [str(event_id)],
        "confidence": 1.0,
        "payload": {
            "tenant_id": str(tenant_id),
            "policy_version": report.get("policy_version"),
            "n": int(report.get("n") or 0),
        },
    }


def _success_outcome(
    *,
    delivery: Any,
    completion_event_id: str,
    tenant_id: str,
    report: dict[str, Any],
) -> dict[str, Any]:
    ledger_evidence = _completion_evidence(
        event_id=completion_event_id,
        tenant_id=tenant_id,
        report=report,
    )
    delivery_evidence = _delivery_evidence(delivery)
    delivery_ok = bool(delivery.get("ok")) if isinstance(delivery, Mapping) else bool(delivery)
    verified = bool(
        completion_event_id
        and delivery_ok
        and _proof_is_positive(delivery_evidence)
    )
    return {
        "ok": verified,
        "status": "verified" if verified else "failed",
        "report": dict(report),
        "completion_event_id": completion_event_id,
        "delivery": delivery,
        "router_evidence": ledger_evidence if verified else None,
        "feedback": {
            "connector_snapshots": [ledger_evidence, delivery_evidence]
            if verified and delivery_evidence is not None
            else []
        },
    }


def handle_ads_rl_train_tick(
    payload: dict[str, Any],
    effects: EffectsPort,
    env: Any,
    *,
    event_store: Any,
) -> Any:
    body = dict(payload or {})
    bind_runtime_state(event_store=event_store)
    tenant_id = str(as_tenant_id(_required_text(body, "tenant_id")))
    user_id = _required_text(body, "user_id")
    decision_id = str(env.decision.decision_id)
    correlation_id = str(env.decision.correlation_id)

    completed = _load_completion(
        event_store=event_store,
        tenant_id=tenant_id,
        decision_id=decision_id,
    )
    if completed is not None:
        report, completion_event_id = completed
        delivery = _send(
            effects=effects,
            body=body,
            tenant_id=tenant_id,
            user_id=user_id,
            decision_id=decision_id,
            correlation_id=correlation_id,
            text=(
                "✅ RL Train: "
                f"policy_version={report.get('policy_version')}, "
                f"n={report.get('n')}, "
                f"avg_reward_minor={report.get('avg_reward_minor')}"
            ),
            track_event_type="ads_rl_train_ok@v1",
            track_payload={
                "policy_version": report.get("policy_version"),
                "n": report.get("n"),
                "avg_reward_minor": report.get("avg_reward_minor"),
                "completion_event_id": completion_event_id,
                "replayed": True,
            },
        )
        return _success_outcome(
            delivery=delivery,
            completion_event_id=completion_event_id,
            tenant_id=tenant_id,
            report=report,
        )

    lookback_days = int(body.get("lookback_days") or 14)
    decision_ids = [
        str(item)
        for item in (body.get("decision_ids") or [])
        if str(item).strip()
    ]
    if not decision_ids:
        delivery = _send(
            effects=effects,
            body=body,
            tenant_id=tenant_id,
            user_id=user_id,
            decision_id=decision_id,
            correlation_id=correlation_id,
            text="🧠 RL Train: нет decision_ids для обучения (передай список выполненных решений).",
            track_event_type="ads_rl_train_skipped@v1",
            track_payload={"reason": "no_decision_ids"},
        )
        return _skipped_outcome(
            delivery=delivery,
            reason="no_decision_ids",
        )

    matured = [
        item
        for item in decision_ids
        if maturity_gate.is_mature(
            tenant_id=tenant_id,
            decision_id=item,
        )
    ]
    minimum_matured = max(5, int(body.get("min_matured") or 5))
    if len(matured) < minimum_matured:
        report = {
            "matured": len(matured),
            "total": len(decision_ids),
        }
        delivery = _send(
            effects=effects,
            body=body,
            tenant_id=tenant_id,
            user_id=user_id,
            decision_id=decision_id,
            correlation_id=correlation_id,
            text=(
                "⏳ RL Train: недостаточно matured решений "
                f"({len(matured)}/{len(decision_ids)})."
            ),
            track_event_type="ads_rl_train_skipped@v1",
            track_payload={
                "reason": "too_few_matured",
                **report,
            },
        )
        return _skipped_outcome(
            delivery=delivery,
            reason="too_few_matured",
            report=report,
        )

    metrics = ProfitMetricsService(event_store=event_store)
    reward = RewardComputer(
        profit_metrics=metrics,
        window=RewardWindow(pre_days=3, post_days=3),
    )
    builder = DatasetBuilder(reward_computer=reward)
    transitions = builder.build_for_decisions(
        tenant_id=tenant_id,
        decision_ids=matured,
        lookback_days=lookback_days,
    )

    trainer = RLTrainer(
        store=policy_store,
        ope_gate=OPEGate(
            min_transitions=int(body.get("min_transitions") or 30)
        ),
    )
    report_obj = trainer.train(
        tenant_id=tenant_id,
        transitions=transitions,
        user_id=user_id,
        decision_id=decision_id,
        correlation_id=correlation_id,
    )
    report = _report_payload(report_obj)

    try:
        effects.track_event(
            decision_id=decision_id,
            correlation_id=correlation_id,
            user_id=user_id,
            event_type="ads_rl_train_report@v1",
            payload={"tenant_id": tenant_id, **report},
            source="ads_rl",
        )
    except Exception as exc:
        logger.warning(
            "telemetry emission failed",
            extra={"component": __name__, "error": str(exc)},
        )

    if not report["ok"]:
        delivery = _send(
            effects=effects,
            body=body,
            tenant_id=tenant_id,
            user_id=user_id,
            decision_id=decision_id,
            correlation_id=correlation_id,
            text=(
                f"🧠 RL Train: пропуск ({report['reason']}/{report['ope_reason']}) "
                f"n={report['n']}"
            ),
            track_event_type="ads_rl_train_skipped@v1",
            track_payload={
                "reason": report["reason"],
                "ope": report["ope_reason"],
                "n": report["n"],
            },
        )
        return _skipped_outcome(
            delivery=delivery,
            reason=str(report["reason"]),
            report=report,
        )

    completion_event_id = _persist_completion(
        event_store=event_store,
        tenant_id=tenant_id,
        user_id=user_id,
        decision_id=decision_id,
        correlation_id=correlation_id,
        report=report,
    )
    delivery = _send(
        effects=effects,
        body=body,
        tenant_id=tenant_id,
        user_id=user_id,
        decision_id=decision_id,
        correlation_id=correlation_id,
        text=(
            "✅ RL Train: "
            f"policy_version={report['policy_version']}, "
            f"n={report['n']}, avg_reward_minor={report['avg_reward_minor']}"
        ),
        track_event_type="ads_rl_train_ok@v1",
        track_payload={
            "policy_version": report["policy_version"],
            "n": report["n"],
            "avg_reward_minor": report["avg_reward_minor"],
            "completion_event_id": completion_event_id,
        },
    )
    return _success_outcome(
        delivery=delivery,
        completion_event_id=completion_event_id,
        tenant_id=tenant_id,
        report=report,
    )
