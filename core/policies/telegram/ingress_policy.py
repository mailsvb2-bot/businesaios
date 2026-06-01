from __future__ import annotations

from dataclasses import dataclass

from core.policies.telegram.helpers import ProposedAction, propose
from kernel.world_state import WorldStateV1


@dataclass
class TelegramIngressPolicyV1:
    """Ingress policy proposing only Telegram polling.

    This policy is *not* user-facing and must never contain business logic.
    It exists only to request a transport read (getUpdates) through sealed effects.
    """

    id: str = "telegram_ingress" + "@v1"

    def propose(self, state: WorldStateV1) -> ProposedAction:
        # IMPORTANT: This policy must only request a transport read.
        # The runner passes poll parameters through WorldState.session.
        sess = state.session or {}
        payload = {
            "offset": sess.get("offset"),
            "timeout_s": sess.get("timeout_s", 30),
            "limit": sess.get("limit", 50),
        }
        # Keep payload minimal and schema-friendly.
        if payload.get("offset") is None:
            payload.pop("offset", None)
        return propose("poll_telegram_updates@v1", payload)
