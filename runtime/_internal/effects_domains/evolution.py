from __future__ import annotations

from typing import Any

from runtime._internal.effects_tenant import assert_event_log_tenant
from runtime.observability.error_handling import swallow
from runtime.security.runtime_asserts import assert_called_from_executor


def _event_id(event: Any) -> str:
    if isinstance(event, dict):
        return str(event.get("event_id") or "").strip()
    return str(getattr(event, "event_id", "") or "").strip()


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
        user = str(user_id or "").strip()
        kind = str(job_kind or "").strip()
        if not user:
            raise RuntimeError("USER_ID_REQUIRED")
        if not kind:
            raise RuntimeError("JOB_KIND_REQUIRED")

        from runtime.evolution import EvolutionOutbox

        outbox = EvolutionOutbox.from_env()
        job_payload = dict(payload or {})
        job_payload["tenant_id"] = tenant
        job_payload["requested_by"] = user
        job_payload["decision_id"] = str(decision_id)
        job_payload["correlation_id"] = str(correlation_id)
        job_id = outbox.enqueue(job_kind=kind, payload=job_payload)

        event_payload = {
            "tenant_id": tenant,
            "job_id": str(job_id),
            "job_kind": kind,
        }
        event = self.event_log.emit(
            event_type="evolution_job_enqueued",
            source="evolution",
            user_id=user,
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload=event_payload,
        )

        notification: Any = None
        notify_text = job_payload.get("notify_text")
        if isinstance(notify_text, str) and notify_text.strip():
            try:
                notification = self.send_message(  # type: ignore[attr-defined]
                    decision_id=str(decision_id),
                    correlation_id=str(correlation_id),
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

        external_ref = _event_id(event) or f"evolution-job:{tenant}:{job_id}"
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
            "job_id": str(job_id),
            "notification": notification,
            "router_evidence": evidence,
        }
