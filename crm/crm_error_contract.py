from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CrmDomainError(Exception):
    code: str
    message: str
    retryable: bool = False

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"
