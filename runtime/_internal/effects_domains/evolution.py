from __future__ import annotations

from typing import Any, Dict, Optional

from runtime.observability.error_handling import swallow
from runtime.security.runtime_asserts import assert_called_from_executor


class EvolutionEffectsMixin:
    """Evolution bridge: enqueue jobs to outbox (slow loop)."""

    event_log: Any

    def enqueue_evolution_job(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        user_id: str,
        job_kind: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Any:
        assert_called_from_executor()

        from runtime.evolution import EvolutionOutbox

        outbox = EvolutionOutbox.from_env()
        pp = dict(payload or {})
        jid = outbox.enqueue(job_kind=str(job_kind), payload=dict(pp))

        self.event_log.emit(
            event_type="evolution_job_enqueued",
            source="evolution",
            user_id=str(user_id),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload={"job_id": jid, "job_kind": str(job_kind)},
        )

        # Optional UX notify (still within the same sealed runtime effect).
        # IMPORTANT: notify uses send_message, but does NOT change the decision type.
        try:
            chat_id = pp.get("chat_id")
            notify_text = pp.get("notify_text")
            notify_reply_markup = pp.get("notify_reply_markup")
            callback_query_id = pp.get("callback_query_id")
            if chat_id and notify_text:
                self.send_message(  # type: ignore[attr-defined]
                    decision_id=str(decision_id),
                    correlation_id=str(correlation_id),
                    user_id=str(chat_id),
                    text=str(notify_text)[:3500],
                    reply_markup=notify_reply_markup if isinstance(notify_reply_markup, dict) else None,
                    callback_query_id=str(callback_query_id) if callback_query_id else None,
                    channel="telegram",
                )
        except Exception:
            swallow(__name__, 'runtime/_internal/effects_domains/evolution.py')

        return {"ok": True, "job_id": jid}
