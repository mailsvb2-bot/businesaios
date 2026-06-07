from __future__ import annotations

from typing import Any

from .base import AdsConnectorError


async def require_token_compat(
    *,
    tokens: Any,
    tenant_id: str,
    platform: Any,
    account_id: str,
    connector_name: str,
    require_access_token: bool = True,
) -> dict[str, Any]:
    tok = await tokens.get(
        tenant_id=tenant_id,
        platform=platform,
        account_id=account_id,
    )
    if not tok:
        raise AdsConnectorError(
            f"{connector_name}: missing OAuth token for this account"
        )
    token_dict = dict(tok)
    if require_access_token and not token_dict.get("access_token"):
        raise AdsConnectorError(
            f"{connector_name}: token store record is missing access_token"
        )
    return token_dict


__all__ = ["require_token_compat"]
