from __future__ import annotations

class ChannelDeliveryAdapter:
    def send(self, adapter: object, *, request, decision) -> dict[str, object]:
        deliver = getattr(adapter, "deliver", None)
        if not callable(deliver):
            raise TypeError("delivery adapter must implement deliver()")
        return deliver(request=request, decision=decision)
