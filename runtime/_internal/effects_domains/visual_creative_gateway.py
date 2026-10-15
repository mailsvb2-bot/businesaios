from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from typing import Any

_JOB_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,128}")
_SCOPE_ID_RE = re.compile(r"[A-Za-z0-9_.:@/-]{1,160}")


_DIRECTION_FIELDS = ("subject", "action", "setting", "light", "angle", "style", "palette")
_DIRECTION_LABELS = {"light": "Свет", "angle": "Ракурс", "style": "Стиль", "palette": "Палитра"}
_FACT_RE = re.compile(r"\d|%|₽|\$|€|руб|скидк|акци|бесплатн|гаранти|лучш|№|сертифик|наград|отзыв|цена|стоимост", re.I)
VISUAL_NEGATIVE_PROMPT = "водяной знак, надпись, буквы, текст, искажённые руки, размытость, низкое качество"


def visual_direction_prompt(value: object, *, owner_context: str) -> str:
    if not isinstance(value, Mapping) or not set(value) <= set(_DIRECTION_FIELDS):
        raise ValueError("visual_direction_invalid")
    context = owner_context.casefold()
    clean = {}
    for key in _DIRECTION_FIELDS:
        raw = value.get(key, "")
        if not isinstance(raw, str):
            raise ValueError("visual_direction_field_invalid")
        item = " ".join(raw.split())[:120]
        if item and any(match.group(0).casefold() not in context for match in _FACT_RE.finditer(item)):
            item = ""
        clean[key] = item.rstrip(".")
    if not clean["subject"]:
        raise ValueError("visual_direction_subject_required")
    parts = [", ".join(clean[k] for k in ("subject", "action", "setting") if clean[k])]
    parts.extend(f"{_DIRECTION_LABELS[k]}: {clean[k]}" for k in _DIRECTION_LABELS if clean[k])
    while len(prompt := ". ".join(parts) + ".") > 350 and len(parts) > 1:
        parts.pop()
    return prompt[0].upper() + prompt[1:350]


def visual_creative_idempotency_key(*, tenant_id: str, decision_id: str, kind: str, variant: int = 0) -> str:
    tenant = str(tenant_id or "").strip()
    decision = str(decision_id or "").strip()
    visual_kind = str(kind or "").strip().lower()
    if not tenant or not decision or visual_kind not in {"image", "video"}:
        raise ValueError("visual_creative_idempotency_inputs_required")
    raw = (f"{tenant}|{decision}|{visual_kind}" + (f"|v{variant}" if variant else "")).encode()
    return "baios:" + hashlib.sha256(raw).hexdigest()


def visual_creative_job_payload(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not isinstance(value.get("asset_ready"), bool):
        raise RuntimeError("visual_gateway_invalid_response")
    fields = ("id", "provider", "scope_id", "kind", "status", "model", "mime_type", "error_code")
    job: dict[str, Any] = {key: str(value.get(key) or "").strip() for key in fields}
    job["kind"] = job["kind"].lower()
    job["status"] = job["status"].lower()
    job["asset_ready"] = value["asset_ready"]
    job["media_label"] = "animated_banner" if job["provider"] == "yandexart_motion" else job["kind"]
    if _JOB_ID_RE.fullmatch(job["id"]) is None or _SCOPE_ID_RE.fullmatch(job["scope_id"]) is None:
        raise RuntimeError("visual_gateway_invalid_job")
    if job["kind"] not in {"image", "video"} or job["status"] not in {"queued", "running", "succeeded", "failed"}:
        raise RuntimeError("visual_gateway_invalid_job")
    if job["status"] == "succeeded" and job["asset_ready"] is not True:
        raise RuntimeError("visual_gateway_inconsistent_completion")
    return job


def assert_visual_creative_binding(*, tenant_id: str, job: Mapping[str, Any], expected_kind: str = "", expected_job_id: str = "") -> None:
    if str(job.get("scope_id") or "") != str(tenant_id or ""):
        raise RuntimeError("visual_gateway_scope_mismatch")
    if expected_kind and str(job.get("kind") or "") != str(expected_kind):
        raise RuntimeError("visual_gateway_kind_mismatch")
    if expected_job_id and str(job.get("id") or "") != str(expected_job_id):
        raise RuntimeError("visual_gateway_job_id_mismatch")


def visual_creative_evidence(*, tenant_id: str, job: Mapping[str, Any]) -> dict[str, Any]:
    accepted = bool(job.get("id")) and job.get("status") != "failed"
    completed = job.get("status") == "succeeded" and job.get("asset_ready") is True
    code = "visual_creative_completed" if completed else ("visual_creative_job_accepted" if accepted else "visual_creative_failed")
    payload = {"connector": "visual_creative_gateway", "tenant_id": str(tenant_id)}
    payload.update({key: job.get(key) for key in ("scope_id", "provider", "kind", "model", "status", "asset_ready")})
    return {"source": "connector", "verified": accepted, "status": "verified" if accepted else "failed", "code": code, "external_refs": [f"visual-gateway:{job.get('id')}"] if accepted else [], "confidence": 1.0 if accepted else 0.0, "payload": payload}


__all__ = ["assert_visual_creative_binding", "visual_creative_evidence", "visual_creative_idempotency_key", "visual_creative_job_payload", "visual_direction_prompt", "VISUAL_NEGATIVE_PROMPT"]
