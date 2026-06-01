from __future__ import annotations

from typing import Any, Optional, Protocol

MARKETING_COMPOSITION_CONTRACT_VERSION = "MC-CONTRACT-V1"


class MarketingCompositionPort(Protocol):
    async def compose(self, inp: Any) -> str | None: ...
    def compose_sync(self, inp: Any) -> str | None: ...
