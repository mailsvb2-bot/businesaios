from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from application.business_autonomy.contracts import (
    BusinessCapability,
    BusinessExecutionRequest,
    BusinessExecutionResult,
    IntegrationMode,
)


class ExternalBusinessAdapter(Protocol):
    @property
    def adapter_name(self) -> str: ...

    @property
    def business_id(self) -> str: ...

    def supported_modes(self) -> Sequence[IntegrationMode]: ...

    def declared_capabilities(self) -> Sequence[BusinessCapability]: ...

    async def execute(self, request: BusinessExecutionRequest) -> BusinessExecutionResult: ...
