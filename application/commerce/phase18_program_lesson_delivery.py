"""Phase-18 program delivery verification against *existing* approved outbound truth.

This service neither issues decisions nor queues a provider send. It uses the
same approval archive, provider execution history and customer identity owners
as the canonical outbound runtime. Provider acceptance != recipient delivery.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

CANON_PHASE18_LESSON_DELIVERY_VERIFIER = True

_RECIPIENT_FIELD = {
    "telegram_bot": ("chat_id",),
    "vk_messaging": ("peer_id",),
    "max_messaging": ("user_id", "chat_id"),
    "email_connector": ("recipient",),
    "whatsapp_cloud": ("to",),
}


def _recipient_and_text(*, provider_key: str, payload: Mapping[str, Any]) -> tuple[str, str]:
    fields = _RECIPIENT_FIELD.get(provider_key, ())
    recipient = next((str(payload.get(key) or "").strip() for key in fields
                      if str(payload.get(key) or "").strip()), "")
    raw = payload.get("text")
    if isinstance(raw, Mapping):
        message = str(raw.get("body") or "")
    else:
        message = str(raw or payload.get("message") or payload.get("body") or "")
    return recipient, message


def reconcile_program_lesson_provider_acceptance(
    *, programs, provider_admin_handlers, tenant_id: str, business_id: str,
    program_id: str, enrollment_id: str, lesson_position: int,
    channel: str, approval_id: str,
) -> dict[str, object]:
    """Resolve approved canonical send; never trust user-supplied delivery flags."""
    plan = programs.lesson_send_plan(
        tenant_id=tenant_id, business_id=business_id,
        program_id=program_id, enrollment_id=enrollment_id,
        lesson_position=lesson_position, channel=channel,
    )
    if provider_admin_handlers is None:
        raise RuntimeError("program_delivery_verifier_unavailable")
    approval_id = str(approval_id or "").strip()
    if not approval_id:
        raise ValueError("program_delivery_approval_id_required")
    record = provider_admin_handlers.approval_store_factory().get(approval_id)
    if record is None or str(record.request.tenant_id) != tenant_id:
        raise KeyError("program_delivery_approval_not_found")
    meta = dict(record.request.metadata or {})
    action = f'provider.{plan["provider_key"]}.message_send'
    if str(meta.get("action_name") or "") != action:
        raise ValueError("program_delivery_approval_action_mismatch")
    if str(getattr(record.status, "value", record.status)) != "approved":
        return {"status": "awaiting_owner_approval", "provider_accepted": False,
                "recipient_delivery_confirmed": False}
    decision_id = str(meta.get("decision_id") or "").strip()
    fingerprint = str(meta.get("approval_request_fingerprint") or "").strip()
    if not decision_id or not fingerprint:
        raise RuntimeError("program_delivery_approval_provenance_missing")
    context = meta.get("approval_resume_context")
    if not isinstance(context, Mapping) or (
        str(context.get("business_id") or "") != business_id
        or str(context.get("provider_key") or "") != plan["provider_key"]
        or str(context.get("operation") or "") != "message_send"
        or not isinstance(context.get("payload"), Mapping)
    ):
        raise ValueError("program_delivery_approval_scope_or_payload_mismatch")
    approved_recipient, approved_text = _recipient_and_text(
        provider_key=str(plan["provider_key"]), payload=context["payload"],
    )
    if (approved_recipient, approved_text) != (plan["recipient"], plan["text"]):
        raise ValueError("program_delivery_approval_content_mismatch")
    envelope = provider_admin_handlers.decision_loader(
        tenant_id=tenant_id, decision_id=decision_id,
    )
    decision = getattr(envelope, "decision", None)
    if decision is None or str(getattr(decision, "decision_id", "")) != decision_id or (
        str(getattr(decision, "action", "")) != "send_message@v1"
    ):
        raise RuntimeError("program_delivery_canonical_decision_missing")
    archived = dict(getattr(decision, "payload", {}) or {})
    if (
        str(archived.get("business_id") or "") != business_id
        or str(archived.get("provider_key") or "") != plan["provider_key"]
        or str(archived.get("user_id") or "") != plan["recipient"]
        or str(archived.get("text") or "") != plan["text"]
    ):
        raise ValueError("program_delivery_decision_content_mismatch")
    queue_job_id = f'provider-sync-{plan["provider_key"]}-{fingerprint[:32]}'
    history = provider_admin_handlers._service(business_id).find_provider_sync_history_jobs(
        tenant_id=tenant_id, business_id=business_id,
        provider_key=plan["provider_key"], queue_job_ids=(queue_job_id,),
    )
    row = history.get(queue_job_id)
    if not row:
        return {"status": "awaiting_provider_evidence", "provider_accepted": False,
                "recipient_delivery_confirmed": False}
    if (
        str(row.get("tenant_id") or "") != tenant_id
        or str(row.get("business_id") or "") != business_id
        or str(row.get("provider_key") or "") != plan["provider_key"]
        or str(row.get("queue_job_id") or "") != queue_job_id
        or str(row.get("operation") or "") != "message_send"
        or str(row.get("mode") or "") != "live"
    ):
        raise RuntimeError("program_delivery_provider_history_scope_invalid")
    parsed = dict(row.get("parsed_response") or {})
    accepted = bool(row.get("accepted")) and row.get("status") == "live_executed"
    resource_id = str(parsed.get("resource_id") or "").strip()
    if not accepted or not resource_id:
        return {"status": "provider_not_confirmed", "provider_accepted": False,
                "recipient_delivery_confirmed": False}
    history_id = str(row.get("history_id") or "").strip()
    raw_time = str(row.get("recorded_at_utc") or "").strip()
    try:
        recorded_at = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
        if recorded_at.tzinfo is None:
            raise ValueError("timezone required")
        recorded_at_ms = int(recorded_at.timestamp() * 1000)
    except (ValueError, OverflowError) as exc:
        raise RuntimeError("program_delivery_provider_timestamp_missing") from exc
    if not history_id or recorded_at_ms < 1:
        raise RuntimeError("program_delivery_provider_evidence_incomplete")
    observed = programs.record_provider_acceptance(
        tenant_id=tenant_id, business_id=business_id,
        program_id=program_id, enrollment_id=enrollment_id,
        lesson_position=lesson_position, provider_key=plan["provider_key"],
        approval_id=approval_id, decision_id=decision_id,
        provider_message_id=resource_id, history_id=history_id,
        recorded_at_ms=recorded_at_ms,
    )
    return {
        "status": "provider_accepted", "provider_accepted": True,
        "recipient_delivery_confirmed": False,
        "lesson_completion_confirmed": False,
        "outcome": observed,
    }


__all__ = ["CANON_PHASE18_LESSON_DELIVERY_VERIFIER", "reconcile_program_lesson_provider_acceptance"]
