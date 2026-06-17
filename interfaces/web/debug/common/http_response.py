from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    body: object
    headers: Mapping[str, str] | None = None
    content_type: str = ""

    def __post_init__(self) -> None:
        if self.content_type and self.headers is None:
            object.__setattr__(self, "headers", {"content-type": self.content_type})


__all__ = ["HttpResponse"]
