from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from runtime.business_autonomy.provider_media import (
    ProviderMediaPreparationCoordinator,
    provider_media_file_digest,
)
from runtime.handler_loader import import_internal_attr

CANON_PROVIDER_VK_MEDIA_HTTP = True


def _sync_request(**kwargs: Any):
    return import_internal_attr("runtime._internal.http_transport", "sync_request")(**kwargs)


def _sync_multipart_file(**kwargs: Any):
    return import_internal_attr("runtime._internal.http_transport", "sync_multipart_file")(**kwargs)


def _form(data: Mapping[str, Any]) -> bytes:
    return import_internal_attr("runtime._internal.http_transport", "form_urlencode")(dict(data))


def _json_mapping(result: Any) -> dict[str, Any]:
    payload = getattr(result, "json", None)
    if isinstance(payload, Mapping):
        return dict(payload)
    text = str(getattr(result, "text", "") or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except Exception:
        return {}
    return dict(parsed) if isinstance(parsed, Mapping) else {}


def _vk_call(*, method: str, params: Mapping[str, Any], access_token: str, timeout_seconds: float, provider_base_url: str) -> dict[str, Any]:
    result = _sync_request(
        method="POST",
        url=f"{provider_base_url.rstrip('/')}/{method}",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=_form({**dict(params), "access_token": access_token, "v": "5.199"}),
        timeout_s=timeout_seconds,
    )
    payload = _json_mapping(result)
    if int(getattr(result, "status", 0) or 0) != 200 or payload.get("error"):
        raise ConnectionError(f"VK media preparation failed: {method}")
    return payload


def _attachment_from_save(payload: Mapping[str, Any]) -> str:
    response = payload.get("response")
    candidates = response if isinstance(response, list) else [response]
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        doc = candidate.get("doc") or candidate.get("audio_message") or candidate
        if not isinstance(doc, Mapping):
            continue
        owner_id, doc_id = doc.get("owner_id"), doc.get("id")
        if owner_id is None or doc_id is None:
            continue
        attachment = f"doc{owner_id}_{doc_id}"
        access_key = str(doc.get("access_key") or "").strip()
        return attachment + (f"_{access_key}" if access_key else "")
    raise ValueError("VK docs.save returned no attachment identity")


def _audio_attachment(payload: Mapping[str, Any]) -> tuple[str, str, str] | None:
    raw = payload.get("attachments")
    if not isinstance(raw, list) or not raw:
        return None
    items = [dict(item) for item in raw if isinstance(item, Mapping)]
    if len(items) != 1:
        raise ValueError("VK canonical audio send requires exactly one attachment")
    item = items[0]
    media_kind = str(item.get("kind") or item.get("type") or "").strip().casefold()
    if media_kind not in {"audio", "voice"}:
        raise ValueError("VK canonical media attachment type is unsupported")
    source = str(item.get("source") or item.get("path") or "").strip()
    if not source:
        raise ValueError("VK canonical media attachment source is required")
    upload_type = "audio_message" if Path(source).suffix.lower() in {".ogg", ".opus"} else "doc"
    return source, upload_type, str(item.get("source_digest") or "").strip().lower()


def prepare_vk_audio_attachment(
    *,
    tenant_id: str,
    business_id: str,
    queue_job_id: str,
    peer_id: str,
    payload: Mapping[str, Any],
    access_token: str,
    media_preparation: ProviderMediaPreparationCoordinator,
    timeout_seconds: float,
    provider_base_url: str,
) -> str | None:
    descriptor = _audio_attachment(payload)
    if descriptor is None:
        return None
    source, upload_type, source_digest = descriptor
    base_url = str(provider_base_url or "").strip().rstrip("/")
    if not base_url.startswith("https://"):
        raise ValueError("VK provider base URL must use HTTPS")
    job_id = str(queue_job_id or "").strip()
    if not job_id:
        raise ValueError("VK media send requires durable queue job identity")
    source_digest = source_digest or provider_media_file_digest(source)
    media_type = f"audio:{upload_type}"
    prepared = media_preparation.read(
        tenant_id=tenant_id,
        business_id=business_id,
        provider_key="vk_messaging",
        job_id=job_id,
        media_type=media_type,
        source_digest=source_digest,
    )
    if prepared is not None:
        return prepared.remote_token

    actual_digest = provider_media_file_digest(source)
    if actual_digest != source_digest:
        raise ValueError("VK media source changed after approval/enqueue")
    upload_meta = _vk_call(
        method="docs.getMessagesUploadServer",
        params={"peer_id": str(peer_id), "type": upload_type},
        access_token=access_token,
        timeout_seconds=timeout_seconds,
        provider_base_url=base_url,
    )
    response = upload_meta.get("response")
    upload_url = str(response.get("upload_url") or "").strip() if isinstance(response, Mapping) else ""
    if not upload_url:
        raise ValueError("VK media upload URL missing")
    uploaded_result = _sync_multipart_file(
        url=upload_url,
        path=source,
        field_name="file",
        timeout_s=max(30.0, timeout_seconds),
    )
    uploaded = _json_mapping(uploaded_result)
    if int(getattr(uploaded_result, "status", 0) or 0) != 200:
        raise ConnectionError("VK media multipart upload failed")
    uploaded_file = str(uploaded.get("file") or "").strip()
    if not uploaded_file:
        raise ValueError("VK media upload returned no file token")
    saved = _vk_call(
        method="docs.save",
        params={"file": uploaded_file, "title": Path(source).stem[:128], "tags": "businessaios,audio"},
        access_token=access_token,
        timeout_seconds=timeout_seconds,
        provider_base_url=base_url,
    )
    attachment = _attachment_from_save(saved)
    media_preparation.store_prepared(
        tenant_id=tenant_id,
        business_id=business_id,
        provider_key="vk_messaging",
        job_id=job_id,
        media_type=media_type,
        source_digest=source_digest,
        remote_token=attachment,
    )
    return attachment


__all__ = ["CANON_PROVIDER_VK_MEDIA_HTTP", "prepare_vk_audio_attachment"]
