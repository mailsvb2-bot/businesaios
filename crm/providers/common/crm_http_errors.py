from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class CrmHttpErrorContext:
    method: str
    url: str
    status_code: int | None = None
    response_headers: Mapping[str, str] = field(default_factory=dict)
    response_text: str | None = None
    attempt: int = 1


class CrmHttpError(RuntimeError):
    def __init__(self, message: str, *, context: CrmHttpErrorContext) -> None:
        super().__init__(message)
        self.context = context


class CrmTimeoutError(CrmHttpError):
    pass


class CrmTransportError(CrmHttpError):
    pass


class CrmResponseError(CrmHttpError):
    pass


class CrmRateLimitError(CrmResponseError):
    pass


class CrmAuthenticationError(CrmResponseError):
    pass
