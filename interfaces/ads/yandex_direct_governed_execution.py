"""Yandex Direct governed execution adapter for the existing AdsWriteGateway.

This is NOT a second publisher. Registration and live writes remain disabled
until provider credentials, capability certification and owner approval exist.
Injected transport must be the canonical sealed effects HTTP provider.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from interfaces.ads.base import AdsPlatform
from interfaces.ads.yandex_direct_publication_proof import (
    DirectAdIdentity, parse_ads_add_receipt, prepare_ads_add, prepare_ads_get,
    verify_ads_get, validate_publication_context,
)

ProviderTransport = Callable[..., Awaitable[Mapping[str, Any]]]


def _required(label: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > 180:
        raise ValueError(f"direct_{label}_invalid")
    return value


@dataclass(frozen=True)
class DirectPublicationBinding:
    tenant_id: str
    business_id: str
    account_id: str
    publication_job_id: str
    execution_reference: str
    approval_reference: str
    campaign_id: int
    ad_group_id: int
    image_hash: str
    title: str
    description: str
    destination_url: str

    def __post_init__(self):
        for key in ("tenant_id", "business_id", "account_id", "publication_job_id",
                    "execution_reference", "approval_reference"):
            _required(key, getattr(self, key))
        validate_publication_context(
            tenant_id=self.tenant_id, business_id=self.business_id,
            account_id=self.account_id, approval_reference=self.approval_reference,
            execution_reference=self.execution_reference, campaign_id=self.campaign_id,
            ad_group_id=self.ad_group_id, image_hash=self.image_hash)
        prepare_ads_add(ad_group_id=self.ad_group_id, title=self.title,
                        description=self.description, destination_url=self.destination_url,
                        image_hash=self.image_hash)


class GovernedYandexDirectConnector:
    """Opt-in adapter. Only the canonical gateway may call create_or_update.

    Transport callable is supplied by existing sealed effects and authenticates
    against a pre-bound provider account. No raw token, client-login or URL enters
    the mutable publication payload.
    """

    platform = AdsPlatform.YANDEX_DIRECT

    def __init__(self, *, binding: DirectPublicationBinding,
                 send: ProviderTransport, read: ProviderTransport):
        if not callable(send) or not callable(read):
            raise ValueError("direct_provider_transport_required")
        self.binding, self._send, self._read = binding, send, read

    async def create_or_update(self, *, tenant_id: str, account_id: str,
                               object_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        bound = self.binding
        if tenant_id != bound.tenant_id or account_id != bound.account_id or object_type != "ad":
            raise PermissionError("direct_publication_scope_mismatch")
        expected = {"name": bound.title, "text": bound.description,
                    "href": bound.destination_url, "image": bound.image_hash}
        if type(payload) is not dict or payload != expected:
            raise PermissionError("direct_publication_payload_changed")
        request = prepare_ads_add(
            ad_group_id=bound.ad_group_id, title=bound.title,
            description=bound.description, destination_url=bound.destination_url,
            image_hash=bound.image_hash)
        response = await self._send(account_id=bound.account_id, request=request)
        ad_id = parse_ads_add_receipt(response)
        # Returning a provider ID only acknowledges creation: the canonical
        # reviewed publication gateway MUST perform independent readback.
        return {"status": "accepted", "object_id": str(ad_id)}

    async def verify_created_ad(self, *, tenant_id: str, business_id: str,
                                platform: str, account_id: str, publication_job_id: str,
                                object_id: str, asset: Any) -> dict[str, Any]:
        bound = self.binding
        if (tenant_id, business_id, platform, account_id, publication_job_id) != (
            bound.tenant_id, bound.business_id, "yandex_direct",
            bound.account_id, bound.publication_job_id):
            raise PermissionError("direct_readback_scope_mismatch")
        if (getattr(asset, "provider_image_hash", None) != bound.image_hash
                or getattr(asset, "tenant_id", None) != bound.tenant_id
                or getattr(asset, "business_id", None) != bound.business_id
                or getattr(asset, "publication_job_id", None) != bound.publication_job_id):
            raise PermissionError("direct_readback_asset_mismatch")
        if not isinstance(object_id, str) or not object_id.isascii() or not object_id.isdecimal():
            raise ValueError("direct_readback_id_invalid")
        ad_id = int(object_id)
        request = prepare_ads_get(ad_id)
        response = await self._read(account_id=bound.account_id, request=request)
        return verify_ads_get(response, expected=DirectAdIdentity(
            ad_id=ad_id, ad_group_id=bound.ad_group_id,
            campaign_id=bound.campaign_id, media_hash=bound.image_hash,
            destination_url=bound.destination_url))
