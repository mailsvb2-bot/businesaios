from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass

from runtime import effects as runtime_effects


@dataclass(frozen=True)
class RetryPolicy:
    attempts: int = 4
    base_delay_seconds: float = 0.25
    max_delay_seconds: float = 4.0
    retry_statuses: frozenset[int] = frozenset({408, 425, 429, 500, 502, 503, 504})

    def __post_init__(self) -> None:
        if self.attempts < 1:
            raise ValueError("retry attempts must be at least 1")
        if self.base_delay_seconds < 0 or self.max_delay_seconds < 0:
            raise ValueError("retry delays must be non-negative")


@dataclass(frozen=True)
class ReadOnlyHttpResponse:
    status_code: int
    text: str


class ExternalProviderError(RuntimeError):
    def __init__(self, message: str, *, provider_key: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.provider_key = provider_key
        self.status_code = status_code


class ReadOnlyHttpTransport:
    """Read-only market sensor transport routed through the canonical runtime effects facade.

    Some provider query APIs use POST for retrieval. ``post_json`` is therefore
    allowed only as a sensor operation; the provider layer still never opens
    sockets itself and real network I/O stays behind ``runtime.effects``.
    """

    def __init__(
        self,
        *,
        provider_key: str,
        timeout_seconds: float = 15.0,
        retry: RetryPolicy | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.provider_key = provider_key
        self._timeout = timeout_seconds
        self._retry = retry or RetryPolicy()

    def get(
        self,
        url: str,
        *,
        params: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> ReadOnlyHttpResponse:
        last_status: int | None = None
        for attempt in range(self._retry.attempts):
            try:
                response = runtime_effects.http_get(
                    url=url,
                    params=dict(params or {}),
                    headers=dict(headers or {}),
                    timeout_s=max(1, int(round(self._timeout))),
                )
            except RuntimeError as exc:
                # In particular, BUSINESAIOS_ALLOW_NETWORK=0 must fail closed
                # immediately instead of being retried as if it were provider load.
                raise ExternalProviderError(
                    f"{self.provider_key} runtime network effect unavailable",
                    provider_key=self.provider_key,
                ) from exc

            status = int(getattr(response, "status", 0) or 0)
            last_status = status or None
            if status > 0 and status not in self._retry.retry_statuses:
                if status >= 400:
                    raise ExternalProviderError(
                        f"{self.provider_key} request failed with HTTP {status}",
                        provider_key=self.provider_key,
                        status_code=status,
                    )
                return ReadOnlyHttpResponse(status_code=status, text=str(getattr(response, "text", "")))

            if attempt + 1 < self._retry.attempts:
                delay = min(
                    self._retry.max_delay_seconds,
                    self._retry.base_delay_seconds * (2**attempt),
                )
                time.sleep(delay)

        raise ExternalProviderError(
            f"{self.provider_key} retry budget exhausted",
            provider_key=self.provider_key,
            status_code=last_status,
        )
    def post_json(
        self,
        url: str,
        *,
        payload: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> ReadOnlyHttpResponse:
        last_status: int | None = None
        for attempt in range(self._retry.attempts):
            try:
                response = runtime_effects.http_json(
                    "POST",
                    url,
                    dict(payload or {}),
                    headers=dict(headers or {}),
                    timeout_s=max(1, int(round(self._timeout))),
                )
            except RuntimeError as exc:
                raise ExternalProviderError(
                    f"{self.provider_key} runtime network effect unavailable",
                    provider_key=self.provider_key,
                ) from exc

            status = int(getattr(response, "status", 0) or 0)
            last_status = status or None
            if status > 0 and status not in self._retry.retry_statuses:
                if status >= 400:
                    raise ExternalProviderError(
                        f"{self.provider_key} request failed with HTTP {status}",
                        provider_key=self.provider_key,
                        status_code=status,
                    )
                return ReadOnlyHttpResponse(
                    status_code=status,
                    text=str(getattr(response, "text", "")),
                )

            if attempt + 1 < self._retry.attempts:
                delay = min(
                    self._retry.max_delay_seconds,
                    self._retry.base_delay_seconds * (2**attempt),
                )
                time.sleep(delay)

        raise ExternalProviderError(
            f"{self.provider_key} retry budget exhausted",
            provider_key=self.provider_key,
            status_code=last_status,
        )
