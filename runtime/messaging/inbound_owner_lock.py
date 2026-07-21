from __future__ import annotations

CANON_MESSAGING_INBOUND_OWNER_LOCK = True

_PROVIDER_WEBHOOK_OWNER = "runtime.business_autonomy.provider_webhook_inbound_processor"
_RUNTIME_ENTRYPOINT_OWNER = "runtime.messaging.inbound_entrypoint"
_WEB_CHAT_NORMALIZATION_OWNER = "interfaces.web.chat_widget.api_handlers"

_ALLOWED_INBOUND_ENTRYPOINTS = frozenset(
    {
        _RUNTIME_ENTRYPOINT_OWNER,
        _PROVIDER_WEBHOOK_OWNER,
        _WEB_CHAT_NORMALIZATION_OWNER,
    }
)
_ALLOWED_INBOUND_DECISION_ENTRYPOINTS = frozenset(
    {
        _RUNTIME_ENTRYPOINT_OWNER,
        _PROVIDER_WEBHOOK_OWNER,
    }
)


class MessagingInboundOwnerLockError(RuntimeError):
    pass


class InboundOwnerViolation(MessagingInboundOwnerLockError):
    pass


def _normalized_caller(caller: str) -> str:
    return str(caller or "").strip()


def assert_inbound_owner(caller: str) -> None:
    normalized = _normalized_caller(caller)
    if normalized not in _ALLOWED_INBOUND_ENTRYPOINTS:
        raise MessagingInboundOwnerLockError(f"messaging_inbound_requires_canonical_owner:{normalized}")


def assert_inbound_decision_owner(caller: str) -> None:
    normalized = _normalized_caller(caller)
    if normalized not in _ALLOWED_INBOUND_DECISION_ENTRYPOINTS:
        raise InboundOwnerViolation(
            f"canonical_messaging_inbound_requires_canonical_owner:{normalized}"
        )


__all__ = [
    "CANON_MESSAGING_INBOUND_OWNER_LOCK",
    "InboundOwnerViolation",
    "MessagingInboundOwnerLockError",
    "assert_inbound_decision_owner",
    "assert_inbound_owner",
]
