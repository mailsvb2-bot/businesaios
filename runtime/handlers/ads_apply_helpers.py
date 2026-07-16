from __future__ import annotations

from typing import Any

from core.events.event_types import is_known
from runtime.ads import (
    DECISION_EXECUTED,
    AdsApplyRequest,
    AdsApplyState,
    AdsCommand,
    AdsPlan,
    IdempotencyKey,
)
from runtime.tenancy import as_tenant_id


def decode_ads_plan(raw: Any) -> AdsPlan:
    commands = []
    data = raw.get("plan") if isinstance(raw, dict) else raw
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            commands.append(
                AdsCommand(
                    platform=str(item.get("platform") or ""),
                    action=str(item.get("action") or "apply_plan"),
                    payload=dict(item.get("payload") or {}),
                )
            )
    return AdsPlan(commands=commands, notes="decoded")


def build_apply_request(payload: dict[str, Any]) -> tuple[AdsApplyRequest, AdsApplyState, str, str]:
    tenant_id = as_tenant_id(str(payload.get("tenant_id") or ""))
    user_id = str(payload.get("user_id") or "")
    idem_key = str(payload.get("idempotency_key") or "")
    plan = decode_ads_plan(payload.get("plan") or payload.get("commands") or payload.get("steps") or [])
    gate_settings = payload.get("gate_settings") if isinstance(payload.get("gate_settings"), dict) else {}
    req = AdsApplyRequest(
        tenant_id=tenant_id,
        user_id=user_id,
        plan=plan,
        idempotency=IdempotencyKey(tenant_id=tenant_id, key=idem_key),
        dry_run=bool(payload.get("dry_run", True)),
        rollback_on_fail=bool(payload.get("rollback_on_fail", True)),
        reason=str(payload.get("reason") or "manual"),
    )
    return req, AdsApplyState.from_settings(gate_settings), str(tenant_id), user_id


def summary_text(*, status: str, detail: dict[str, Any]) -> str:
    if status == "dry_run":
        return (
            "🧪 Ads Apply: DRY-RUN\n\n"
            f"План: {int(detail.get('planned_changes') or 0)} изменений\n"
            f"Бюджет (minor): {int(detail.get('planned_budget_minor') or 0)}\n\n"
            "Чтобы применить — нужен явный enable + apply без dry-run."
        )
    if status == "applied":
        return "✅ Ads Apply: применено."
    if status == "duplicate":
        return "♻️ Ads Apply: дубликат (idempotency)."
    if status == "blocked":
        return f"🛑 Ads Apply: заблокировано ({detail.get('error')})."
    if status == "failed":
        return "❌ Ads Apply: ошибка. (rollback best-effort, см. аудит)."
    return f"Ads Apply: {status}"


def emit_apply_audit(
    *,
    effects: Any,
    payload: dict[str, Any],
    user_id: str,
    audit_event: dict[str, Any],
) -> None:
    raw_event_type = str(audit_event.get("event_type") or "ads_apply_audit@v1")
    event_type = raw_event_type if is_known(raw_event_type) else "ads_apply_executed@v1"
    event_payload = dict(audit_event.get("payload") or {})
    event_payload.setdefault("tenant_id", str(payload.get("tenant_id") or ""))
    if event_type != raw_event_type:
        event_payload["engine_audit_event_type"] = raw_event_type
        event_payload["event_type_normalized"] = True
    effects.track_event(
        decision_id=str(payload.get("decision_id") or ""),
        correlation_id=str(payload.get("correlation_id") or ""),
        user_id=user_id,
        event_type=event_type,
        payload=event_payload,
        source=str(audit_event.get("source") or "ads"),
    )


def emit_apply_success_governance(
    *,
    effects: Any,
    payload: dict[str, Any],
    user_id: str,
) -> None:
    effects.track_event(
        decision_id=str(payload.get("decision_id") or ""),
        correlation_id=str(payload.get("correlation_id") or ""),
        user_id=user_id,
        event_type=DECISION_EXECUTED,
        payload={
            "tenant_id": str(payload.get("tenant_id") or ""),
            "domain": "ads.apply",
            "status": "applied",
        },
        source="governance",
    )
