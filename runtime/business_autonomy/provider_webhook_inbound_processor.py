from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from runtime.messaging.inbound_decision_gateway import MessagingInboundDecisionGateway, process_inbound_gateway_message
from runtime.messaging.inbound_message import InboundMessage

CANON_PROVIDER_WEBHOOK_INBOUND_PROCESSOR = True


@dataclass(frozen=True)
class ProviderWebhookInboundProcessor:
    decision_core: object
    executor: object | None = None

    def process(self, *, handoff: Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(handoff or {}).get("inbound_message") or {}
        if not isinstance(payload, Mapping) or not payload:
            return {}
        metadata = dict(payload.get("metadata") or {})
        for identity in ("tenant_id", "channel", "user_id", "chat_id"):
            if identity in metadata and str(metadata[identity]) != str(payload.get(identity) or ""):
                raise RuntimeError("provider_inbound_identity_mismatch")
        metadata.pop("business_id", None)  # Never trust webhook business attribution.
        gateway = MessagingInboundDecisionGateway(
            decision_core=self.decision_core, caller='runtime.business_autonomy.provider_webhook_inbound_processor',
        )
        message = InboundMessage(
            tenant_id=str(payload.get('tenant_id') or ''),
            channel=str(payload.get('channel') or ''),
            user_id=str(payload.get('user_id') or ''),
            text=str(payload.get('text') or ''),
            correlation_id=str(payload.get('correlation_id') or ''),
            transport_message_id=str(payload.get('transport_message_id') or ''),
            external_user_ref=str(payload.get('external_user_ref') or payload.get('user_id') or ''),
            metadata={**metadata, 'source': 'provider_webhook_handoff', 'chat_id': str(payload.get('chat_id') or '')},
        )
        envelope = process_inbound_gateway_message(gateway=gateway, message=message)
        result = {'accepted': True, 'decision_envelope': envelope}
        if self.executor is not None and envelope is not None:
            from runtime.execution.execution_path_lock import execute_locked_decision, lock_execution_envelope
            execution = execute_locked_decision(
                executor=self.executor, locked_path=lock_execution_envelope(envelope=envelope),
            )
            confirmed = execution.get("ok") if isinstance(execution, Mapping) else getattr(execution, "ok", None)
            if confirmed is not True:
                raise RuntimeError("provider_inbound_execution_unconfirmed")
            result['execution'] = execution
        return result


__all__ = ['CANON_PROVIDER_WEBHOOK_INBOUND_PROCESSOR', 'ProviderWebhookInboundProcessor']
