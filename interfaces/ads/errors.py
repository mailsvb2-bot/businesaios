from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class AdsConnectorError(RuntimeError):
    """Base connector error."""

@dataclass(frozen=True)
class AuthError(AdsConnectorError):
    message: str
    platform: str | None = None

@dataclass(frozen=True)
class RateLimitError(AdsConnectorError):
    message: str
    retry_after_s: int | None = None
    platform: str | None = None

@dataclass(frozen=True)
class QuotaError(AdsConnectorError):
    message: str
    platform: str | None = None

@dataclass(frozen=True)
class ValidationError(AdsConnectorError):
    message: str
    field: str | None = None
    platform: str | None = None

@dataclass(frozen=True)
class TransportError(AdsConnectorError):
    message: str
    status: int | None = None
    platform: str | None = None
