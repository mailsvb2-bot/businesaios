"""Bridge approved donor media receipts into the existing guarded ads gateway.

This performs NO write itself. Publication still requires the canonical
approval/reservation/provider-readback authorities in ads_write_gateway.
"""
from __future__ import annotations

from typing import Mapping

from application.visual_creative_semantics.phase18_advertising_studio import (
    AdvertisingCreativeBrief, require_approved_visual_result,
)
from bootstrap.ads_write_gateway import ReviewedAdPublication
from contracts.ad_publication_asset import (
    AdAssetKind, AdAssetSource, AdAssetState, AdPublicationAssetEvidence,
)


def prepare_reviewed_generated_ad(
    *, brief: AdvertisingCreativeBrief, approved_fingerprint: str,
    receipt: Mapping[str, object], publication_job_id: str,
    platform: str, account_id: str, approval_reference: str,
    execution_reference: str, destination_url: str,
) -> ReviewedAdPublication:
    require_approved_visual_result(
        brief=brief, approved_fingerprint=approved_fingerprint, receipt=receipt,
    )
    provider_field = "provider_image_hash" if brief.kind == "image" else "provider_video_id"
    provider_id = receipt.get(provider_field)
    content_type = receipt.get("content_type")
    size_bytes = receipt.get("size_bytes")
    if not isinstance(provider_id, str) or not provider_id.strip():
        raise RuntimeError("advertising_media_provider_proof_missing")
    if not isinstance(content_type, str) or type(size_bytes) is not int:
        raise RuntimeError("advertising_media_metadata_missing")
    if not isinstance(destination_url, str) or not destination_url.startswith("https://"):
        raise ValueError("advertising_destination_https_required")
    asset = AdPublicationAssetEvidence(
        tenant_id=brief.tenant_id, business_id=brief.business_id,
        publication_job_id=publication_job_id, asset_id=brief.creative_id,
        kind=AdAssetKind(brief.kind), source=AdAssetSource.GENERATED,
        content_type=content_type, sha256=str(receipt["sha256"]),
        size_bytes=size_bytes, state=AdAssetState.READY,
        **{provider_field: provider_id},
    )
    field = "image" if brief.kind == "image" else "video"
    return ReviewedAdPublication(
        tenant_id=brief.tenant_id, business_id=brief.business_id,
        publication_job_id=publication_job_id, platform=platform,
        account_id=account_id, object_type="ad",
        payload={
            "name": brief.headline, "text": brief.description,
            "href": destination_url, field: provider_id,
        },
        asset=asset, approval_reference=approval_reference,
        execution_reference=execution_reference,
    )


__all__ = ["prepare_reviewed_generated_ad"]
