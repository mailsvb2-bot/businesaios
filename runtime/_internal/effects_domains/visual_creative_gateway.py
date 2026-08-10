from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from typing import Any

_JOB_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,128}")
_SCOPE_ID_RE = re.compile(r"[A-Za-z0-9_.:@/-]{1,160}")


def visual_creative_idempotency_key(*, tenant_id: str, decision_id: str, kind: str) -> str:
    tenant = str(tenant_id or "").strip()
    decision = str(decision_id or "").strip()
    visual_kind = str(kind or "").strip().lower()
    if not tenant or not decision or visual_kind not in {"image", "video"}:
        raise ValueError("visual_creative_idempotency_inputs_required")
    digest = hashlib.sha256(f"{tenant}|{decision}|{visual_kind}".encode()).hexdigest()
    return f"baios:{digest}"


def visual_creative_job_payload(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeError("visual_gateway_invalid_response")
    job = {
        "id": str(value.get("id") or "").strip(),
        "provider": str(value.get("provider") or "").strip(),
        "scope_id": str(value.get("scope_id") or "").strip(),
        "kind": str(value.get("kind") or "").strip().lower(),
        "status": str(value.get("status") or "").strip().lower(),
        "model": str(value.get("model") or "").strip(),
        "mime_type": str(value.get("mime_type") or "").strip(),
        "error_code": str(value.get("error_code") or "").strip(),
        "asset_ready": bool(value.get("asset_ready")),
    }
    if (
        _JOB_ID_RE.fullmatch(job["id"]) is None
        or _SCOPE_ID_RE.fullmatch(job["scope_id"]) is None
        or job["kind"] not in {"image", "video"}
        or job["status"] not in {"queued", "running", "succeeded", "failed"}
    ):
        raise RuntimeError("visual_gateway_invalid_job")
    if job["status"] == "succeeded" and not job["asset_ready"]:
        raise RuntimeError("visual_gateway_inconsistent_completion")
    return job


def assert_visual_creative_scope(*, tenant_id: str, job: Mapping[str, Any]) -> None:
    if str(job.get("scope_id") or "") != str(tenant_id or ""):
        raise RuntimeError("visual_gateway_scope_mismatch")


def assert_visual_creative_job_id(*, expected_job_id: str, job: Mapping[str, Any]) -> None:
    if str(job.get("id") or "") != str(expected_job_id or ""):
        raise RuntimeError("visual_gateway_job_id_mismatch")


def visual_creative_evidence(*, tenant_id: str, job: Mapping[str, Any]) -> dict[str, Any]:
    accepted = str(job.get("status") or "") != "failed" and bool(job.get("id"))
    completed = str(job.get("status") or "") == "succeeded" and bool(job.get("asset_ready"))
    return {
        "source": "connector",
        "verified": accepted,
        "status": "verified" if accepted else "failed",
        "code": (
            "visual_creative_completed"
            if completed
            else ("visual_creative_job_accepted" if accepted else "visual_creative_failed")
        ),
        "external_refs": [f"visual-gateway:{job.get('id')}"] if accepted else [],
        "confidence": 1.0 if accepted else 0.0,
        "payload": {
            "connector": "visual_creative_gateway",
            "tenant_id": str(tenant_id),
            "scope_id": str(job.get("scope_id") or ""),
            "provider": str(job.get("provider") or ""),
            "kind": str(job.get("kind") or ""),
            "model": str(job.get("model") or ""),
            "status": str(job.get("status") or ""),
            "asset_ready": bool(job.get("asset_ready")),
        },
    }


__all__ = [
    "assert_visual_creative_job_id",
    "assert_visual_creative_scope",
    "visual_creative_evidence",
    "visual_creative_idempotency_key",
    "visual_creative_job_payload",
]
