
from __future__ import annotations

from dataclasses import dataclass

from interfaces.telegram.telegram_action_mapper import map_telegram_message_to_action
from interfaces.telegram.telegram_action_models import (
    TelegramIncomingMessage,
    TelegramOutgoingMessage,
)
from runtime.messaging.inbound_entrypoint import handle_inbound_message
from runtime.messaging.inbound_message import InboundMessage


@dataclass(frozen=True)
class TelegramHandler:
    application_service: object | None = None
    decision_core: object | None = None

    def _handle_via_decision_core(self, incoming: TelegramIncomingMessage) -> TelegramOutgoingMessage:
        handle_inbound_message(
            decision_core=self.decision_core,
            message=InboundMessage(
                tenant_id=str(dict(incoming.metadata or {}).get('tenant_id') or 'default'),
                channel='telegram',
                user_id=str(incoming.user_id),
                text=str(incoming.text),
                payload=dict(incoming.metadata or {}),
                correlation_id=str(dict(incoming.metadata or {}).get('correlation_id') or ''),
                transport_message_id=str(dict(incoming.metadata or {}).get('message_id') or ''),
                metadata=dict(incoming.metadata or {}),
            )
        )
        return TelegramOutgoingMessage(
            chat_id=incoming.chat_id,
            text='Decision accepted.',
        )

    def _handle_via_application_service(self, incoming: TelegramIncomingMessage) -> TelegramOutgoingMessage:
        action = map_telegram_message_to_action(incoming)
        result = self.application_service.execute_action(action)

        if result['status'] == 'blocked':
            text = 'Action blocked by governance.'
        else:
            text = 'Action accepted.'

        return TelegramOutgoingMessage(
            chat_id=incoming.chat_id,
            text=text,
        )

    def handle_message(
        self,
        incoming: TelegramIncomingMessage,
    ) -> TelegramOutgoingMessage:
        if self.decision_core is not None:
            return self._handle_via_decision_core(incoming)
        if self.application_service is None:
            raise RuntimeError('telegram_handler_requires_decision_core_or_application_service')
        return self._handle_via_application_service(incoming)
