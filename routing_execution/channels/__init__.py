from __future__ import annotations

from config.execution_contract import (
    STUB_DELIVERY_DETAIL,
    STUB_DELIVERY_PUBLIC_DETAIL,
    STUB_DELIVERY_STATUS,
)

CANON_DELIVERY_CHANNEL_COMPAT_SHIM = True

class StaticSuccessDelivery:
    CHANNEL = ''
    IS_STUB = True

    def deliver(self, *, request, decision) -> dict[str, object]:
        status = STUB_DELIVERY_STATUS if self.IS_STUB else 'ok'
        detail = STUB_DELIVERY_PUBLIC_DETAIL if self.IS_STUB else STUB_DELIVERY_DETAIL
        return {
            'channel': self.CHANNEL,
            'status': status,
            'request_id': request.request_id,
            'business_id': decision.selected_business_id or '',
            'detail': detail,
            'stub_detail': STUB_DELIVERY_DETAIL,
            'stub': self.IS_STUB,
        }

class CallCenterDelivery(StaticSuccessDelivery):
    CHANNEL = "call_center"

class CrmDelivery(StaticSuccessDelivery):
    CHANNEL = "crm"

class EmailDelivery(StaticSuccessDelivery):
    CHANNEL = "email"

class InternalMarketplaceDelivery(StaticSuccessDelivery):
    CHANNEL = "internal_marketplace"

class SmsDelivery(StaticSuccessDelivery):
    CHANNEL = "sms"

class TelegramDelivery(StaticSuccessDelivery):
    CHANNEL = "telegram"

class WhatsappDelivery(StaticSuccessDelivery):
    CHANNEL = "whatsapp"

DELIVERY_CHANNEL_COMPAT_EXPORTS = {
    '_base': {'StaticSuccessDelivery': 'routing_execution.channels:StaticSuccessDelivery'},
    'call_center_delivery': {'CallCenterDelivery': 'routing_execution.channels:CallCenterDelivery'},
    'crm_delivery': {'CrmDelivery': 'routing_execution.channels:CrmDelivery'},
    'email_delivery': {'EmailDelivery': 'routing_execution.channels:EmailDelivery'},
    'internal_marketplace_delivery': {'InternalMarketplaceDelivery': 'routing_execution.channels:InternalMarketplaceDelivery'},
    'sms_delivery': {'SmsDelivery': 'routing_execution.channels:SmsDelivery'},
    'telegram_delivery': {'TelegramDelivery': 'routing_execution.channels:TelegramDelivery'},
    'whatsapp_delivery': {'WhatsappDelivery': 'routing_execution.channels:WhatsappDelivery'},
}

__all__ = [
    'CANON_DELIVERY_CHANNEL_COMPAT_SHIM',
    'DELIVERY_CHANNEL_COMPAT_EXPORTS',
    'CallCenterDelivery',
    'CrmDelivery',
    'EmailDelivery',
    'InternalMarketplaceDelivery',
    'SmsDelivery',
    'StaticSuccessDelivery',
    'TelegramDelivery',
    'WhatsappDelivery',
]
