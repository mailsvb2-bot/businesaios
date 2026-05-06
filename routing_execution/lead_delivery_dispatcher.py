from __future__ import annotations

import time

from contracts.matching.delivery_outcome import DeliveryOutcome
from observability.demand import emit_delivery_events as emit_delivery_event
from routing_execution.lead_delivery_registry import LeadDeliveryRegistry
from routing_execution.lead_delivery_retry import LeadDeliveryRetry
from routing_execution.lead_delivery_idempotency import LeadDeliveryIdempotency
from routing_execution.channel_delivery_adapter import ChannelDeliveryAdapter
from routing_execution.channel_selector import ChannelSelector
from routing_execution.business_notification_dispatcher import BusinessNotificationDispatcher
from routing_execution.customer_confirmation_dispatcher import CustomerConfirmationDispatcher
from routing_execution.delivery_contract_validator import DeliveryContractValidator
from routing_execution.delivery_status import delivered_at_ms_for_status, normalize_delivery_status
from routing_execution.channels.crm_delivery import CrmDelivery
from routing_execution.channels.email_delivery import EmailDelivery
from routing_execution.channels.sms_delivery import SmsDelivery
from routing_execution.channels.telegram_delivery import TelegramDelivery
from routing_execution.channels.whatsapp_delivery import WhatsappDelivery
from routing_execution.channels.call_center_delivery import CallCenterDelivery
from routing_execution.channels.internal_marketplace_delivery import InternalMarketplaceDelivery


class LeadDeliveryDispatcher:
    def __init__(self, *, event_log: object | None = None) -> None:
        self._registry = LeadDeliveryRegistry()
        for adapter in (CrmDelivery(), EmailDelivery(), SmsDelivery(), TelegramDelivery(), WhatsappDelivery(), CallCenterDelivery(), InternalMarketplaceDelivery()):
            self._registry.register(adapter.CHANNEL, adapter)
        self._retry = LeadDeliveryRetry()
        self._idem = LeadDeliveryIdempotency()
        self._adapter = ChannelDeliveryAdapter()
        self._selector = ChannelSelector()
        self._validator = DeliveryContractValidator()
        self._biz_notify = BusinessNotificationDispatcher()
        self._cust_confirm = CustomerConfirmationDispatcher()
        self._event_log = event_log

    def _normalize_outcome(self, raw: object, *, request_id: str, business_id: str, channel: str) -> dict[str, object]:
        if not isinstance(raw, dict):
            raise ValueError('delivery adapter must return a dict')
        status = normalize_delivery_status(raw.get('status'))
        detail = str(raw.get('detail') or '').strip() or status
        return {
            'request_id': request_id,
            'business_id': business_id,
            'channel': channel,
            'status': status,
            'detail': detail,
            'stub': bool(raw.get('stub', False)),
            'stub_detail': str(raw.get('stub_detail') or '').strip(),
        }

    def dispatch(self, *, request, decision) -> DeliveryOutcome | None:
        if decision.selected_business_id is None:
            emit_delivery_event(self._event_log, 'delivery_skipped', {'request_id': request.request_id, 'reason': 'manual_review'})
            return None
        available_channels = tuple(name for name, _ in self._registry.items())
        channel = self._selector.choose(request=request, decision=decision, available_channels=available_channels)
        self._validator.validate(request=request, decision=decision, channel=channel)
        if not self._idem.claim(request.request_id, decision.selected_business_id):
            emit_delivery_event(self._event_log, 'delivery_duplicate', {'request_id': request.request_id, 'business_id': decision.selected_business_id})
            return DeliveryOutcome(request.request_id, decision.selected_business_id, 'duplicate', channel, 'idempotent duplicate', None)
        adapter = self._registry.get(channel)
        if adapter is None:
            raise RuntimeError(f'missing delivery adapter for channel: {channel}')
        raw = self._retry.run(lambda: self._adapter.send(adapter, request=request, decision=decision))
        normalized = self._normalize_outcome(raw, request_id=request.request_id, business_id=decision.selected_business_id, channel=channel)
        if not bool(normalized['stub']):
            self._biz_notify.notify(business_id=decision.selected_business_id, channel=channel)
            self._cust_confirm.confirm(request_id=request.request_id, business_id=decision.selected_business_id)
        delivered_at_ms = delivered_at_ms_for_status(str(normalized['status']), now_ms=int(time.time() * 1000))
        outcome = DeliveryOutcome(
            request_id=request.request_id,
            business_id=decision.selected_business_id,
            delivery_status=str(normalized['status']),
            channel=channel,
            detail=str(normalized['detail']),
            delivered_at_ms=delivered_at_ms,
        )
        event_name = 'delivery_transport_not_configured' if bool(normalized['stub']) else 'delivery_dispatched'
        emit_delivery_event(
            self._event_log,
            event_name,
            {
                'request_id': request.request_id,
                'business_id': decision.selected_business_id,
                'channel': channel,
                'stub': bool(normalized.get('stub', False)),
                'detail': str(normalized.get('detail') or ''),
                'stub_detail': str(normalized.get('stub_detail') or ''),
            },
        )
        return outcome
