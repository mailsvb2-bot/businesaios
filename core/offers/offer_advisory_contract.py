from __future__ import annotations

from typing import Any, Protocol

OFFER_ADVISORY_CONTRACT_VERSION = "OA-CONTRACT-V1"


class OfferAdvisoryPort(Protocol):
    def decide_offer(self, *args: Any, **kwargs: Any) -> Any: ...
