"""VK/MAX inbound helpers. Transport verification lives in the existing generic ingress
(``/providers/webhook/...`` -> ProviderWebhookRuntime: VK secret/confirmation, MAX header secret);
this module only persists the route secrets there and maps promotion start payloads."""

from __future__ import annotations

from typing import Any

from application.business_autonomy.provider_catalog import provider_map
from application.business_flows import native_channels as nc
from application.business_flows import promotions as pm
from security.secret_contract import SecretRecord, SecretRef, SecretSource


def persist_route_secrets(vault, *, platform: str, tenant_id: str, business_id: str, webhook_secret: str,
                          confirmation_code: str | None = None, group_id: str | None = None) -> list[str]:  # fmt: skip
    """Write the secrets the existing ProviderWebhookRuntime reads; returns secret names (never values)."""
    provider = provider_map()[nc.PROVIDER_KEYS[platform]]
    cid = provider.connector_id
    values = {"webhook_secret": webhook_secret, "confirmation_code": confirmation_code, "group_id": group_id}
    names = []
    for name, value in values.items():
        if value:
            ref = SecretRef(tenant_id=tenant_id, connector_id=cid, scope=business_id, secret_name=f"{cid}.{name}")
            vault.put(SecretRecord(ref=ref, ciphertext=b"pending", source=SecretSource.CONNECTOR), plaintext=str(value).encode())
            names.append(f"{cid}.{name}")
    return names


def promotion_touch(*, camps: dict[str, pm.Campaign], text: str, platform: str, subject: str,
                    identities: dict[tuple[str, str], str]) -> dict[str, Any] | None:  # fmt: skip
    """``/start cpa_<token>`` (or bare payload) from a known VK/MAX identity -> verified opened fact."""
    word = str(text or "").replace("/start", "").strip()
    token = pm.parse_start_payload(word)
    if token is None:
        return None
    return pm.open_channel_for_identity(
        camps, token, platform=platform, external_subject=subject, identities=identities
    )[1]
