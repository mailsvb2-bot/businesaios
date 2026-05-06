from __future__ import annotations
from typing import Any
from runtime.firewall.capability import issue_capability
from runtime.ports.effects import EffectsPort
from runtime.security.capability_gate import GuardedEffectsPort

class _NoopDeliveryState:
    def is_delivered(self, message_id: str) -> bool: return False
    def mark_delivered(self, message_id: str) -> None: return None

def build_guarded_effects(*, effects_cls: Any, event_log: Any, policy_registry: Any, delivery_state: Any = None, ledger: Any = None, payment_outbox: Any = None, telegram_outbound_queue: Any = None, settings_gateway: Any = None, messaging_policy_event_store: Any = None, messaging_policy_read_service: Any = None, http_transport: Any = None, effect_router: Any = None) -> tuple[str, EffectsPort]:
    cap = issue_capability(); cap_token = cap.token
    raw: EffectsPort = effects_cls(
        event_log=event_log, policy_registry=policy_registry, delivery_state=delivery_state or _NoopDeliveryState(), ledger=ledger,
        payment_outbox=payment_outbox, telegram_outbound_queue=telegram_outbound_queue, settings_gateway=settings_gateway,
        messaging_policy_event_store=messaging_policy_event_store, messaging_policy_read_service=messaging_policy_read_service,
        http_transport=http_transport, effect_router=effect_router,
    )
    return cap_token, GuardedEffectsPort(cap_token, raw)
