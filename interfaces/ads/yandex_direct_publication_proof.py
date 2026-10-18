"""Yandex Direct API v5 publication proof, without an independent publisher.

The caller is the canonical AdsWriteGateway owner. This module only validates
provider envelopes and prepares a non-mutating Ads.get request. It cannot approve,
reserve, publish, spend, or infer publication from an Ads.add receipt.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

YANDEX_ADS_ENDPOINT = "https://api.direct.yandex.com/json/v5/ads"
CANON_YANDEX_PUBLICATION_PROOF_ONLY = True


@dataclass(frozen=True, slots=True)
class DirectAdIdentity:
    ad_id: int
    ad_group_id: int
    campaign_id: int
    media_hash: str
    destination_url: str


def _positive_id(value: object, field: str) -> int:
    if type(value) is not int or not 0 < value <= 2**63 - 1:
        raise ValueError(f"direct_{field}_invalid")
    return value


def prepare_ads_get(ad_id: int) -> dict[str, object]:
    """Exactly one provider object, never a broad account enumeration."""
    return {
        "method": "get",
        "params": {
            "SelectionCriteria": {"Ids": [_positive_id(ad_id, "ad_id")]},
            "FieldNames": ["Id", "CampaignId", "AdGroupId", "Status", "State", "Type"],
            "ResponsiveAdFieldNames": ["AdImages"],
        },
    }


def parse_ads_add_receipt(response: object) -> int:
    """A provider write acknowledgement is NOT a proof of published delivery."""
    if not isinstance(response, Mapping) or response.get("error") is not None:
        raise RuntimeError("direct_add_provider_error")
    result = response.get("result")
    rows = result.get("AddResults") if isinstance(result, Mapping) else None
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], Mapping):
        raise RuntimeError("direct_add_receipt_ambiguous")
    row = rows[0]
    if row.get("Errors") or row.get("Warnings"):
        raise RuntimeError("direct_add_receipt_requires_review")
    return _positive_id(row.get("Id"), "created_id")


def verify_ads_get(
    response: object, *,
    expected: DirectAdIdentity,
) -> dict[str, Any]:
    """Fail closed on identity, campaign, creative image, status or ambiguity.

    Moderation acceptance is distinct from delivery. Only an ON/ACCEPTED ad with
    the exact immutable creative reference can be reported provider_verified.
    """
    if not isinstance(response, Mapping) or response.get("error") is not None:
        raise RuntimeError("direct_get_provider_error")
    result = response.get("result")
    rows = result.get("Ads") if isinstance(result, Mapping) else None
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], Mapping):
        raise RuntimeError("direct_get_ambiguous")
    row = rows[0]
    if any(row.get(field) != target for field, target in (
        ("Id", _positive_id(expected.ad_id, "ad_id")),
        ("CampaignId", _positive_id(expected.campaign_id, "campaign_id")),
        ("AdGroupId", _positive_id(expected.ad_group_id, "ad_group_id")),
    )):
        raise PermissionError("direct_get_identity_mismatch")
    if row.get("Type") != "RESPONSIVE_AD":
        raise RuntimeError("direct_get_ad_type_mismatch")
    media = row.get("ResponsiveAd")
    images = media.get("AdImages") if isinstance(media, Mapping) else None
    if not isinstance(images, list) or len(images) != 1:
        raise RuntimeError("direct_get_media_ambiguous")
    if not isinstance(images[0], Mapping) or images[0].get("AdImageHash") != expected.media_hash:
        raise PermissionError("direct_get_media_mismatch")
    status, state = row.get("Status"), row.get("State")
    if status not in {"ACCEPTED", "DRAFT", "MODERATION", "REJECTED"}:
        raise RuntimeError("direct_get_status_unknown")
    if state not in {"ON", "OFF", "SUSPENDED", "ARCHIVED"}:
        raise RuntimeError("direct_get_state_unknown")
    if status == "REJECTED":
        return {"verified": False, "status": "rejected", "object_id": str(expected.ad_id)}
    if status != "ACCEPTED" or state != "ON":
        return {"verified": False, "status": "pending", "object_id": str(expected.ad_id)}
    return {"verified": True, "status": "provider_verified", "object_id": str(expected.ad_id)}


def validate_publication_context(
    *, tenant_id: str, business_id: str, account_id: str,
    approval_reference: str, execution_reference: str,
    ad_group_id: int, campaign_id: int, image_hash: str,
) -> DirectAdIdentity:
    """Require explicit scoped authority fields before handing off to the owner."""
    for label, value in (
        ("tenant", tenant_id), ("business", business_id), ("account", account_id),
        ("approval", approval_reference), ("execution", execution_reference),
    ):
        if not isinstance(value, str) or not value.strip() or len(value) > 160:
            raise ValueError(f"direct_{label}_missing")
    _positive_id(ad_group_id, "ad_group_id")
    _positive_id(campaign_id, "campaign_id")
    if not isinstance(image_hash, str) or not 5 <= len(image_hash) <= 256 or any(ord(c) < 33 for c in image_hash):
        raise ValueError("direct_image_hash_invalid")
    return DirectAdIdentity(ad_id=0, ad_group_id=ad_group_id,
                            campaign_id=campaign_id, media_hash=image_hash, destination_url="")


def prepare_ads_add(*, ad_group_id: int, title: str, description: str,
                    destination_url: str, image_hash: str) -> dict[str, object]:
    """Prepare a single combinatorial ad; the canonical gateway owns the write.

    A caller must have separately verified owner approval, campaign/ad-group
    binding, tenant, spending limits and the durable execution reservation.
    """
    from urllib.parse import urlsplit

    _positive_id(ad_group_id, "ad_group_id")
    if not isinstance(title, str) or not title.strip() or len(title) > 56:
        raise ValueError("direct_title_invalid")
    if not isinstance(description, str) or not description.strip() or len(description) > 81:
        raise ValueError("direct_text_invalid")
    if not isinstance(image_hash, str) or not 5 <= len(image_hash) <= 256 or any(ord(c) < 33 for c in image_hash):
        raise ValueError("direct_image_hash_invalid")
    if not isinstance(destination_url, str) or destination_url != destination_url.strip():
        raise ValueError("direct_destination_invalid")
    try:
        parts = urlsplit(destination_url)
        host = parts.hostname
        port = parts.port
    except ValueError as exc:
        raise ValueError("direct_destination_invalid") from exc
    if (parts.scheme != "https" or not host or "." not in host or
            parts.username is not None or parts.password is not None or
            port == 0 or "\\" in destination_url or
            any(ord(c) <= 32 or ord(c) == 127 for c in destination_url)):
        raise ValueError("direct_destination_invalid")
    return {"method": "add", "params": {"Ads": [{
        "AdGroupId": ad_group_id,
        "ResponsiveAd": {
            "Titles": [title.strip()],
            "Texts": [description.strip()],
            "Href": destination_url,
            "AdImageHashes": [image_hash],
        },
    }]}}
