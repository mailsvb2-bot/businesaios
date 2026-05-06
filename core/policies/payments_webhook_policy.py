from __future__ import annotations

from dataclasses import dataclass

from kernel.world_state import WorldStateV1


@dataclass
class PaymentsWebhookReconcilePolicyV1:
    """Policy used for payment webhook reconcile jobs.

    It takes the reconcile job payload from WorldState.meta['job'].
    """

    id: str = "payments_webhook_reconcile" + "@v1"

    def propose(self, state: WorldStateV1):
        meta = getattr(state, "meta", None) or {}
        job = meta.get("job") if isinstance(meta, dict) else None
        job = job if isinstance(job, dict) else {}
        ext_id = job.get("external_id")
        if not ext_id:
            # No-op decision (safe fallback)
            return type("O", (), {"action": "noop@v1", "payload": {}})()
        return type(
            "O",
            (),
            {
                "action": "reconcile_payment@v1",
                "payload": {
                    "external_id": str(ext_id),
                    "notification_id": job.get("notification_id"),
                    "event": job.get("event"),
                    "user_id": job.get("user_id"),
                },
            },
        )()
