from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from runtime.business_autonomy.provider_media import (
    ProviderMediaPreparationCoordinator,
    provider_media_file_digest,
)
from runtime.handler_loader import import_internal_attr

CANON_PROVIDER_MAX_MEDIA_HTTP = True
_MAX_MEDIA_TOKEN_REJECT_CODES = {
    "attachment.invalid",
    "attachment.not.found",
    "attachment.not_found",
    "invalid_attachment",
    "invalid_token",
    "media.not.found",
}


def _sync_request(**kwargs: Any):
    return import_internal_attr("runtime._internal.http_transport", "sync_request")(**kwargs)


def _sync_multipart_file(**kwargs: Any):
    return import_internal_attr("runtime._internal.http_transport", "sync_multipart_file")(**kwargs)


def _single_audio_attachment(payload: Mapping[str, Any]) -> Mapping[str, Any] | None:
    raw = payload.get("attachments")
    if not isinstance(raw, list) or not raw:
        return None
    items = [dict(item) for item in raw if isinstance(item, Mapping)]
    if len(items) != 1:
        raise ValueError("MAX canonical audio send requires exactly one attachment")
    item = items[0]
    media_type = str(item.get("kind") or item.get("type") or "").strip().casefold()
    if media_type not in {"audio", "voice"}:
        raise ValueError("MAX canonical media attachment type is unsupported")
    source = str(item.get("source") or item.get("path") or "").strip()
    if not source:
        raise ValueError("MAX canonical media attachment source is required")
    return {"media_type": "audio", "source": source, "source_digest": str(item.get("source_digest") or "").strip().lower()}


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


def _max_error_code(payload: Mapping[str, Any]) -> str:
    code = payload.get("code")
    error = payload.get("error")
    if not code and isinstance(error, Mapping):
        code = error.get("code")
    return str(code or "").strip().casefold()


def _extract_upload_token(upload_meta: Mapping[str, Any], uploaded: Mapping[str, Any]) -> str:
    candidates: list[Any] = [uploaded.get("token")]
    nested = uploaded.get("payload")
    if isinstance(nested, Mapping):
        candidates.append(nested.get("token"))
    candidates.extend((uploaded.get("audio_token"), uploaded.get("file_token"), upload_meta.get("token")))
    for candidate in candidates:
        token = str(candidate or "").strip()
        if token:
            return token
    raise ValueError("MAX media upload token missing")


def _prepared_retry_response(*, source_digest: str) -> dict[str, Any]:
    parsed = {
        "provider_key": "max_messaging",
        "operation": "message_send",
        "http_status": 425,
        "ok": False,
        "resource_id": None,
        "error_code": "media.prepared",
        "error_message": "media prepared before final provider write",
        "error_category": "media_preparation",
        "retryable": True,
        "retry_after_seconds": 1,
        "delivery_state": "rejected",
        "body_keys": ("code",),
        "normalized_preview": {"code": "media.prepared"},
    }
    return {
        "provider_key": "max_messaging",
        "network_capable": True,
        "http_status": 425,
        "response_body": '{"code":"media.prepared"}',
        "response_headers": {},
        "request": {"method": "PREPARE", "media_type": "audio", "source_digest": source_digest},
        "parsed_response": parsed,
        "_response_ok": False,
        "media_preparation": {"status": "prepared", "source_digest": source_digest, "media_type": "audio"},
    }


def _prepare_media_token(
    *,
    source: str,
    access_token: str,
    timeout_seconds: float,
    provider_base_url: str,
) -> str:
    upload_meta_result = _sync_request(
        method="POST",
        url=f"{provider_base_url.rstrip('/')}/uploads?type=audio",
        headers={"Authorization": access_token},
        body=None,
        timeout_s=timeout_seconds,
    )
    upload_meta = _json_mapping(upload_meta_result)
    status = int(getattr(upload_meta_result, "status", 0) or 0)
    if not 200 <= status < 300 or _max_error_code(upload_meta):
        raise ConnectionError(f"MAX media prepare failed: http_status={status}")
    upload_url = str(upload_meta.get("url") or "").strip()
    if not upload_url:
        direct = str(upload_meta.get("token") or "").strip()
        if direct:
            return direct
        raise ValueError("MAX media upload URL missing")
    uploaded_result = _sync_multipart_file(
        url=upload_url,
        path=source,
        field_name="data",
        timeout_s=max(30.0, timeout_seconds),
    )
    uploaded = _json_mapping(uploaded_result)
    uploaded_status = int(getattr(uploaded_result, "status", 0) or 0)
    if not 200 <= uploaded_status < 300:
        raise ConnectionError(f"MAX media upload failed: http_status={uploaded_status}")
    return _extract_upload_token(upload_meta, uploaded)


def execute_max_media_message(
    *,
    tenant_id: str,
    business_id: str,
    queue_job_id: str,
    payload: Mapping[str, Any],
    access_token: str,
    media_preparation: ProviderMediaPreparationCoordinator,
    timeout_seconds: float,
    provider_base_url: str,
) -> dict[str, Any] | None:
    attachment = _single_audio_attachment(payload)
    if attachment is None:
        return None
    base_url = str(provider_base_url or "").strip().rstrip("/")
    if not base_url.startswith("https://"):
        raise ValueError("MAX provider base URL must use HTTPS")
    job_id = str(queue_job_id or "").strip()
    if not job_id:
        raise ValueError("MAX media send requires durable queue job identity")
    source = str(attachment["source"])
    source_digest = str(attachment.get("source_digest") or "").strip().lower() or provider_media_file_digest(source)
    prepared = media_preparation.read(
        tenant_id=tenant_id,
        business_id=business_id,
        provider_key="max_messaging",
        job_id=job_id,
        media_type="audio",
        source_digest=source_digest,
    )
    if prepared is None:
        actual_digest = provider_media_file_digest(source)
        if actual_digest != source_digest:
            raise ValueError("MAX media source changed after approval/enqueue")
        token = _prepare_media_token(
            source=source,
            access_token=access_token,
            timeout_seconds=timeout_seconds,
            provider_base_url=base_url,
        )
        media_preparation.store_prepared(
            tenant_id=tenant_id,
            business_id=business_id,
            provider_key="max_messaging",
            job_id=job_id,
            media_type="audio",
            source_digest=source_digest,
            remote_token=token,
        )
        return _prepared_retry_response(source_digest=source_digest)
    recipient_key = "chat_id" if str(payload.get("chat_id") or "").strip() else "user_id"
    recipient = str(payload.get(recipient_key) or "").strip()
    if not recipient:
        raise ValueError("MAX media recipient is required")
    url = import_internal_attr("runtime._internal.http_transport", "url_with_params")(
        url=f"{base_url}/messages",
        params={recipient_key: recipient},
    )
    body = {
        "text": str(payload.get("text") or ""),
        "attachments": [{"type": "audio", "payload": {"token": prepared.remote_token}}],
    }
    result = _sync_request(
        method="POST",
        url=url,
        headers={"Authorization": access_token, "Content-Type": "application/json"},
        body=json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
        timeout_s=timeout_seconds,
    )
    response_body = str(getattr(result, "text", "") or "")[:2000]
    body_mapping = _json_mapping(result)
    code = _max_error_code(body_mapping)
    if code in _MAX_MEDIA_TOKEN_REJECT_CODES:
        media_preparation.invalidate(prepared)
    response_headers = {
        str(key): str(value)
        for key, value in dict(getattr(result, "headers", {}) or {}).items()
        if str(key).lower().startswith("x-ratelimit-") or str(key).lower() == "retry-after"
    }
    return {
        "provider_key": "max_messaging",
        "network_capable": True,
        "http_status": int(getattr(result, "status", None) or 599),
        "response_body": response_body,
        "response_headers": response_headers,
        "error_kind": getattr(result, "error_kind", None),
        "error_message": str(getattr(result, "error_message", "") or ""),
        "request": {
            "method": "POST",
            "url": url,
            "headers": {"Authorization": "***", "Content-Type": "application/json"},
            "json_body": {
                "text": body["text"],
                "attachments": [{"type": "audio", "payload": {"token": "***"}}],
            },
        },
        "media_preparation": {
            "status": "final_write",
            "source_digest": source_digest,
            "media_type": "audio",
        },
    }


__all__ = ["CANON_PROVIDER_MAX_MEDIA_HTTP", "execute_max_media_message"]
