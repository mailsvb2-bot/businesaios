from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    body: object
    headers: Mapping[str, str] | None = None


__all__ = ["HttpResponse"]
