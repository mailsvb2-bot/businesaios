from __future__ import annotations

from typing import Any

from .base import AdsConnectorError
from .connector_shared import resolve_secret_required
from .oauth_helper import OAuthAppConfig
from .ports import SecretVault


def resolve_oauth_client_id(
    *,
    oauth: OAuthAppConfig | None,
    vault: SecretVault | None,
    vault_key: str,
    connector_name: str,
    tenant_id: str | None = None,
) -> str:
    return resolve_secret_required(
        cfg_value=oauth.client_id if oauth is not None else None,
        vault=vault,
        vault_key=vault_key,
        error_message=f"{connector_name}: missing cfg or vault",
        tenant_id=tenant_id,
    )


def resolve_oauth_client_secret(
    *,
    oauth: OAuthAppConfig | None,
    vault: SecretVault | None,
    vault_key: str,
    connector_name: str,
    tenant_id: str | None = None,
) -> str:
    return resolve_secret_required(
        cfg_value=oauth.client_secret if oauth is not None else None,
        vault=vault,
        vault_key=vault_key,
        error_message=f"{connector_name}: missing cfg or vault",
        tenant_id=tenant_id,
    )


def resolve_oauth_scope(
    *,
    oauth: OAuthAppConfig | None,
    vault: SecretVault | None,
    vault_key: str,
    default: str,
    tenant_id: str | None = None,
) -> str:
    if oauth is not None and oauth.scopes:
        return str(oauth.scopes)
    if vault is not None:
        try:
            value = vault.get_secret(str(tenant_id), vault_key) if tenant_id else vault.get_secret(vault_key)
        except TypeError:
            value = vault.get_secret(vault_key)
        if value:
            return str(value)
    return str(default)


async def disconnect_tokens_compat(
    *,
    tokens: Any,
    tenant_id: str,
    platform: Any,
    account_id: str,
    connector_name: str,
) -> None:
    if hasattr(tokens, "delete"):
        await tokens.delete(
            tenant_id=tenant_id,
            platform=platform,
            account_id=account_id,
        )
        return
    raise AdsConnectorError(
        f"{connector_name}: disconnect is not supported by current token store"
    )


from datetime import UTC, datetime

from .base import ConnectedAccount


def build_connected_account(*, platform, account_id: str, display_name: str, scope: str) -> ConnectedAccount:
    return ConnectedAccount(
        platform=platform,
        account_id=str(account_id),
        display_name=str(display_name),
        scopes=[str(scope)],
        created_at_iso=datetime.now(UTC).isoformat(),
    )


__all__ = [
    "build_connected_account",
    "disconnect_tokens_compat",
    "resolve_oauth_client_id",
    "resolve_oauth_client_secret",
    "resolve_oauth_scope",
]
