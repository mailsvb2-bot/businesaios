from __future__ import annotations

from typing import Any

from runtime.messaging.inbound_entrypoint import issue_inbound_message_decision
from runtime.messaging.inbound_strict_owner_guard import assert_inbound_owner


class MessagingInboundDecisionGateway:
    def __init__(self, *, decision_core, caller: str):
        self._decision_core = decision_core
        self._caller = str(caller)

    def process(self, *, message):
        """Canonical inbound-message decision entrypoint.

        Provider/webhook surfaces must call this method rather than reaching into
        DecisionCore directly. ``issue`` remains a compatibility alias below so
        older callers do not create a second decision path.
        """
        assert_inbound_owner(self._caller)
        return issue_inbound_message_decision(
            decision_core=self._decision_core,
            message=message,
        )

    def issue(self, *, message):
        return self.process(message=message)


def process_inbound_gateway_message(*, gateway: Any, message: Any) -> Any:
    """Invoke an inbound gateway through the canonical process contract.

    Compatibility gateways used by older tests may still expose ``issue`` only;
    the fallback remains here, inside the inbound gateway owner, so provider
    surfaces do not grow direct issue/DecisionCore bypass calls.
    """
    process = getattr(gateway, "process", None)
    if callable(process):
        return process(message=message)
    issue = getattr(gateway, "issue", None)
    if callable(issue):
        return issue(message=message)
    raise TypeError("INBOUND_DECISION_GATEWAY_CONTRACT_VIOLATION")


__all__ = ["MessagingInboundDecisionGateway", "process_inbound_gateway_message"]
