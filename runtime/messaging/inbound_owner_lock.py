from __future__ import annotations

CANON_MESSAGING_INBOUND_OWNER_LOCK = True

_ALLOWED_INBOUND_ENTRYPOINTS = {
    'runtime.messaging.inbound_entrypoint',
    'runtime.business_autonomy.provider_webhook_inbound_processor',
    'interfaces.web.chat_widget.api_handlers',
}


class MessagingInboundOwnerLockError(RuntimeError):
    pass


def assert_inbound_owner(caller: str) -> None:
    normalized = str(caller or '').strip()
    if normalized not in _ALLOWED_INBOUND_ENTRYPOINTS:
        raise MessagingInboundOwnerLockError(f'messaging_inbound_requires_canonical_owner:{normalized}')
