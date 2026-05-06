from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    content_type: str
    body: Any
