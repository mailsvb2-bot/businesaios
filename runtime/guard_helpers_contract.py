from __future__ import annotations

from typing import Any, Protocol


RUNTIME_GUARD_HELPERS_CONTRACT_VERSION = "RGH-CONTRACT-V1"


class ActionContractRuntimePort(Protocol):
    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...


class EnvelopeVerificationPort(Protocol):
    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...
