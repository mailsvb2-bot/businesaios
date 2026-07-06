"""Shared helpers for OAuth code exchange in ads connectors.

These helpers keep connectors thin and avoid each connector re-implementing the
same token persistence + ConnectedAccount assembly flow. They do not contain
business decisions; they only normalize connector I/O.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from .base import AdsConnectorError, AdsPlatform, ConnectedAccount
from .connector_oauth_helpers import build_connected_account


def _first_present(raw: Mapping[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = raw.get(key)
        if value not in (None, "", [], ()):  # keep 0 valid if it ever appears
            return value
    return None


def extract_access_token(*, raw: Mapping[str, Any], candidate_keys: Sequence[str], connector_name: str) -> str:
    token = _first_present(raw, candidate_keys)
    if token is None and isinstance(raw.get("data"), Mapping):
        token = _first_present(raw["data"], candidate_keys)
    if token in (None, ""):
        raise AdsConnectorError(f"{connector_name}: token exchange failed (no access_token)")
    return str(token)


async def persist_connected_account(
    *,
    platform: AdsPlatform,
    tenant_id: str,
    account_id: str,
    access_token: str,
    scope: str,
    display_name: str,
    tokens_put: Any,
) -> ConnectedAccount:
    await tokens_put(
        tenant_id=tenant_id,
        account_id=str(account_id),
        access_token=str(access_token),
        scope=scope,
    )
    return build_connected_account(
        platform=platform,
        account_id=str(account_id),
        display_name=display_name,
        scope=scope,
    )


__all__ = ["extract_access_token", "persist_connected_account"]
