from __future__ import annotations

import uuid
from typing import Any

from runtime._internal.effects_tenant import assert_event_log_tenant
from runtime.observability.error_handling import swallow
from runtime.security.runtime_asserts import assert_called_from_executor

_EVOLUTION_ID_NAMESPACE = uuid.UUID("fcdf7c59-2b24-453f-b3bd-c1f22fdfd63d")


def _event_id(event: Any) -> str:
    if isinstance(event, dict):
        return str(event.get("event_id") or "").strip()
    return str(getattr(event, "event_id", "") or "").strip()


def _stable_id(*, purpose: str, tenant_id: str, decision_id: str, job_kind: str) -> str:
    return str(
        uuid.uuid5(
            _EVOLUTION_ID_NAMESPACE,
            f"{purpose}:{tenant_id}:{decision_id}:{job_kind}",
        )
    )


def _existing_enqueue_event(
    event_log: Any,
    *,
    decision_id: str,
    event_id: str,
    expected_payload: dict[str, Any],
) -> bool:
    get_events = getattr(event_log, "get_events", None)
    if not callable(get_events):
        return False
    try:
        events = list(get_events(str(decision_id), "evolution_job_enqueued") or [])
    except Exception:
        return False
    for event in events:
        if not isinstance(event, dict):
            continue
        if str(event.get("event_id") or "") != str(event_id):
            continue
        if dict(event.get("payload") or {}) == dict(expected_payload):
            return True
    return False


def _emit_enqueue_event_once(
    event_log: Any,
    *,
    event_id: str,
    decision_id: str,
    correlation_id: str,
    user_id: str,
    payload: dict[str, Any],
) -> str:
    try:
        event = event_log.emit(
            event_id=str(event_id),
            event_type="evolution_job_enqueued",
            source="evolution",
            user_id=str(user_id),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload=dict(payload),
        )
        return _event_id(event) or str(event_id)
    except Exception:
        if _existing_enqueue_event(
            event_log,
            decision_id=str(decision_id),
            event_id=str(event_id),
            expected_payload=dict(payload),
        ):
            return str(event_id)
        raise


class EvolutionEffectsMixin:
    """Evolution bridge: enqueue tenant-scoped jobs to the slow-loop outbox."""

    event_log: Any

    def enqueue_evolution_job(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        tenant_id: str,
        user_id: str,
        job_kind: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert_called_from_executor()
        tenant = assert_event_log_tenant(
            self.event_log,
            tenant_id=str(tenant_id),
            operation="enqueue_evolution_job",
        )
        decision = str(decision_id or "").strip()
        correlation = str(correlation_id or "").strip()
        user = str(user_id or "").strip()
        kind = str(job_kind or "").strip()
        if not decision:
            raise RuntimeError("DECISION_ID_REQUIRED")
        if not correlation:
            raise RuntimeError("CORRELATION_ID_REQUIRED")
        if not user:
            raise RuntimeError("USER_ID_REQUIRED")
        if not kind:
            raise RuntimeError("JOB_KIND_REQUIRED")

        from runtime.evolution import EvolutionOutbox

        job_id = _stable_id(
            purpose="job",
            tenant_id=tenant,
            decision_id=decision,
            job_kind=kind,
        )
        audit_event_id = _stable_id(
            purpose="event",
            tenant_id=tenant,
            decision_id=decision,
            job_kind=kind,
        )
        job_payload = dict(payload or {})
        job_payload["tenant_id"] = tenant
        job_payload["requested_by"] = user
        job_payload["decision_id"] = decision
        job_payload["correlation_id"] = correlation

        outbox = EvolutionOutbox.from_env()
        persisted_job_id = outbox.enqueue(
            job_kind=kind,
            payload=job_payload,
            job_id=job_id,
        )
        if str(persisted_job_id) != job_id:
            raise RuntimeError("EVOLUTION_OUTBOX_JOB_ID_MISMATCH")

        event_payload = {
            "tenant_id": tenant,
            "job_id": job_id,
            "job_kind": kind,
        }
        external_ref = _emit_enqueue_event_once(
            self.event_log,
            event_id=audit_event_id,
            decision_id=decision,
            correlation_id=correlation,
            user_id=user,
            payload=event_payload,
        )

        notification: Any = None
        notify_text = job_payload.get("notify_text")
        if isinstance(notify_text, str) and notify_text.strip():
            try:
                notification = self.send_message(  # type: ignore[attr-defined]
                    decision_id=decision,
                    correlation_id=correlation,
                    tenant_id=tenant,
                    user_id=str(job_payload.get("notify_user_id") or user),
                    text=notify_text[:3500],
                    reply_markup=(
                        job_payload.get("notify_reply_markup")
                        if isinstance(job_payload.get("notify_reply_markup"), dict)
                        else None
                    ),
                    callback_query_id=(
                        str(job_payload.get("callback_query_id"))
                        if job_payload.get("callback_query_id")
                        else None
                    ),
                    channel="telegram",
                )
            except Exception:
                swallow(__name__, "runtime/_internal/effects_domains/evolution.py")

        evidence = {
            "source": "ledger",
            "verified": True,
            "status": "verified",
            "code": "evolution_job_enqueue_recorded",
            "external_refs": [external_ref],
            "confidence": 1.0,
            "payload": event_payload,
        }
        return {
            "ok": True,
            "status": "verified",
            "job_id": job_id,
            "notification": notification,
            "router_evidence": evidence,
        }
