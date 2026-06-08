from __future__ import annotations

"""Shared ports for Ads connectors.

Why:
  - Prevent duplicated Protocol definitions across connectors ("second lines").
  - Keep connector modules small and focused on normalization logic.
"""

from typing import Any, Optional, Protocol

from .base import AdsPlatform


class SecretVault(Protocol):
    def get_secret(self, key: str) -> str: ...


class TokenStore(Protocol):
    async def put(self, *, tenant_id: str, platform: AdsPlatform, account_id: str, token: dict[str, Any]) -> None: ...
    async def get(self, *, tenant_id: str, platform: AdsPlatform, account_id: str) -> dict[str, Any] | None: ...
    async def delete(self, *, tenant_id: str, platform: AdsPlatform, account_id: str) -> None: ...


class HTTPClient(Protocol):
    async def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]: ...

    async def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...
