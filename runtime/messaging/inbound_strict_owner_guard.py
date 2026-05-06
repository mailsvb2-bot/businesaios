from __future__ import annotations

_ALLOWED_CALLERS = {
    'runtime.messaging.inbound_entrypoint',
    'runtime.business_autonomy.provider_webhook_inbound_processor',
}


class InboundOwnerViolation(RuntimeError):
    pass


def assert_inbound_owner(caller: str) -> None:
    normalized = str(caller or '').strip()
    if normalized not in _ALLOWED_CALLERS:
        raise InboundOwnerViolation(
            f'canonical_messaging_inbound_requires_canonical_owner:{normalized}'
        )
