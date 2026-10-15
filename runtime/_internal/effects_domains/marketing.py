from __future__ import annotations

from typing import Any

from runtime._internal.effects_clients.visual_gateway_client import visual_gateway_json
from runtime._internal.effects_domains.visual_creative_gateway import (
    VISUAL_NEGATIVE_PROMPT,
    visual_direction_prompt,
    assert_visual_creative_binding,
    visual_creative_evidence,
    visual_creative_idempotency_key,
    visual_creative_job_payload,
)
from runtime._internal.effects_tenant import assert_event_log_tenant
from runtime.observability.error_handling import swallow
from runtime.security.runtime_asserts import assert_called_from_executor


def _marketing_copy_evidence(*, decision_id: str, tenant_id: str, admin_id: str, step_key: str) -> dict[str, Any]:
    return {"source": "ledger", "verified": True, "status": "verified", "code": "marketing_copy_recorded", "external_refs": [f"marketing-copy:{tenant_id}:{decision_id}:{admin_id}:{step_key}"], "confidence": 1.0, "payload": {"tenant_id": str(tenant_id), "admin_id": str(admin_id), "step_key": str(step_key)}}


def _visual_identity(*, decision_id: str, correlation_id: str, user_id: str) -> tuple[str, str, str]:
    values = tuple(str(value or "").strip() for value in (decision_id, correlation_id, user_id))
    for value, code in zip(values, ("DECISION_ID_REQUIRED", "CORRELATION_ID_REQUIRED", "USER_ID_REQUIRED"), strict=True):
        if not value:
            raise RuntimeError(code)
    return values  # type: ignore[return-value]


class MarketingEffectsMixin:
    """Marketing runtime hooks and governed copy storage."""

    event_log: Any
    http_transport: Any

    def _visual_tenant(self, tenant_id: str, operation: str) -> str:
        return assert_event_log_tenant(self.event_log, tenant_id=str(tenant_id), operation=operation)

    def _visual_result(self, *, tenant: str, user: str, decision: str, correlation: str, job: dict[str, Any], event_type: str) -> dict[str, Any]:
        self.event_log.emit(event_type=event_type, source="visual_creative", user_id=user, decision_id=decision, correlation_id=correlation, payload={**job, "tenant_id": tenant})
        return {"ok": job["status"] != "failed", "job": job, "router_evidence": visual_creative_evidence(tenant_id=tenant, job=job)}

    def set_marketing_copy(self, *, decision_id: str, correlation_id: str, tenant_id: str, admin_id: str, step_key: str, variant_a: str, variant_b: str, notify_text: str | None = None, notify_reply_markup: dict[str, Any] | None = None, callback_query_id: str | None = None, channel: str = "telegram", channel_policy: dict[str, Any] | None = None) -> Any:
        assert_called_from_executor()
        tenant = assert_event_log_tenant(self.event_log, tenant_id=str(tenant_id), operation="set_marketing_copy")
        if channel == "telegram" and isinstance(callback_query_id, str) and callback_query_id.strip():
            try:
                self._telegram_answer_callback(callback_query_id.strip(), user_id=str(admin_id), decision_id=str(decision_id), correlation_id=str(correlation_id))  # type: ignore[attr-defined]
            except Exception:
                swallow(__name__, "marketing_copy.answer_callback")
        payload = {"tenant_id": tenant, "step_key": str(step_key), "variant_a": str(variant_a)[:2000], "variant_b": str(variant_b)[:2000]}
        self.event_log.emit(event_type="marketing_copy_set", source="marketing", user_id=str(admin_id), decision_id=str(decision_id), correlation_id=str(correlation_id), payload=payload)
        evidence = _marketing_copy_evidence(decision_id=str(decision_id), tenant_id=tenant, admin_id=str(admin_id), step_key=str(step_key))
        notification: Any = None
        if isinstance(notify_text, str) and notify_text.strip():
            try:
                notification = self.send_message(decision_id=str(decision_id), correlation_id=str(correlation_id), tenant_id=tenant, user_id=str(admin_id), text=str(notify_text)[:3500], reply_markup=notify_reply_markup if isinstance(notify_reply_markup, dict) else None, callback_query_id=str(callback_query_id) if callback_query_id else None, channel=str(channel), channel_policy=dict(channel_policy) if isinstance(channel_policy, dict) else None, priority="normal", critical=False)  # type: ignore[attr-defined]
            except Exception as exc:
                notification = {"ok": False, "error": exc.__class__.__name__}
        return {"ok": True, "status": "verified", "copy": payload, "notification": notification, "router_evidence": evidence}

    def generate_visual_creative(self, *, decision_id: str, correlation_id: str, tenant_id: str, user_id: str, kind: str, prompt: str, country_code: str = "", preferred_provider: str = "", aspect_ratio: str = "1:1", duration_seconds: int = 5, negative_prompt: str = "", reference_url: str = "", brand_context: str = "", wait_seconds: int = 0, visual_direction: dict[str, Any] | None = None, seed: int | None = None, variants: int = 1, overlay: dict[str, Any] | None = None) -> dict[str, Any]:
        assert_called_from_executor()
        tenant = self._visual_tenant(tenant_id, "generate_visual_creative")
        decision, correlation, user = _visual_identity(decision_id=decision_id, correlation_id=correlation_id, user_id=user_id)
        visual_kind, visual_prompt = str(kind or "").strip().lower(), str(prompt or "").strip()
        if visual_kind not in {"image", "video"} or not visual_prompt:
            raise ValueError("valid visual kind and prompt are required")
        if visual_direction is not None:
            visual_prompt = visual_direction_prompt(visual_direction, owner_context=f"{visual_prompt} {brand_context}")
            negative_prompt = negative_prompt or VISUAL_NEGATIVE_PROMPT
        if type(variants) is not int or not 1 <= variants <= 4 or (visual_kind == "video" and variants != 1):
            raise ValueError("visual_variants_invalid")
        if seed is not None and (type(seed) is not int or not 0 <= seed <= 2147459889):
            raise ValueError("visual_seed_invalid")
        if overlay is not None and (not isinstance(overlay, dict) or
                not set(overlay) <= {"headline", "body", "cta", "layout", "brand", "formats"}):
            raise ValueError("visual_overlay_invalid")
        wait = max(0, min(int(wait_seconds or 0), 60)) // variants
        request = {"kind": visual_kind, "prompt": visual_prompt, "country_code": str(country_code or ""), "preferred_provider": str(preferred_provider or ""), "aspect_ratio": str(aspect_ratio or "1:1"), "duration_seconds": max(2, min(int(duration_seconds or 5), 15)), "negative_prompt": str(negative_prompt or ""), "reference_url": str(reference_url or ""), "brand_context": str(brand_context or ""), "wait_seconds": wait, "scope_id": tenant}
        jobs = []
        for index in range(variants):
            key = visual_creative_idempotency_key(tenant_id=tenant, decision_id=decision, kind=visual_kind, variant=index)
            variant_seed = None if seed is None and variants == 1 else (seed if seed is not None else 1000) + index * 7919
            payload = {**request, "idempotency_key": key}
            if variant_seed is not None:
                payload["seed"] = variant_seed
            job = visual_creative_job_payload(visual_gateway_json("POST", "/v1/creative/generations", payload, timeout_s=max(30, wait + 15), transport=self.http_transport))
            assert_visual_creative_binding(tenant_id=tenant, job=job, expected_kind=visual_kind)
            if overlay and job["status"] == "succeeded":
                pack = visual_gateway_json("POST", "/v1/creative/render-packs", {"source_job_id": job["id"], "scope_id": tenant, "idempotency_key": key + ":render", "formats": list(overlay.get("formats") or ["feed"]), "composition": {k: v for k, v in overlay.items() if k != "formats"}}, timeout_s=300, transport=self.http_transport)
                job["render_pack"] = {k: pack.get(k) for k in ("id", "status", "error_code")}
            jobs.append(job)
        event_type = "visual_creative_generated" if jobs[0]["status"] == "succeeded" else "visual_creative_submitted"
        result = self._visual_result(tenant=tenant, user=user, decision=decision, correlation=correlation, job=jobs[0], event_type=event_type)
        return {**result, "candidates": jobs} if variants > 1 else result

    def poll_visual_creative(self, *, decision_id: str, correlation_id: str, tenant_id: str, user_id: str, job_id: str) -> dict[str, Any]:
        assert_called_from_executor()
        tenant = self._visual_tenant(tenant_id, "poll_visual_creative")
        decision, correlation, user = _visual_identity(decision_id=decision_id, correlation_id=correlation_id, user_id=user_id)
        token = str(job_id or "").strip()
        if not token or len(token) > 128 or not all(ch.isalnum() or ch in "_-" for ch in token):
            raise ValueError("valid visual job id is required")
        job = visual_creative_job_payload(visual_gateway_json("GET", f"/v1/creative/generations/{token}", {"scope_id": tenant}, timeout_s=30, transport=self.http_transport))
        assert_visual_creative_binding(tenant_id=tenant, job=job, expected_job_id=token)
        return self._visual_result(tenant=tenant, user=user, decision=decision, correlation=correlation, job=job, event_type="visual_creative_polled")

    def _record_variant(self, event_type: str, *, decision_id: str, correlation_id: str, user_id: str, step_key: str, variant: str) -> dict[str, bool]:
        assert_called_from_executor()
        self.event_log.emit(event_type=event_type, source="marketing", user_id=str(user_id), decision_id=str(decision_id), correlation_id=str(correlation_id), payload={"step_key": str(step_key), "variant": str(variant)})
        return {"ok": True}

    def record_variant_shown(self, *, decision_id: str, correlation_id: str, user_id: str, step_key: str, variant: str) -> Any:
        return self._record_variant("variant_shown", decision_id=decision_id, correlation_id=correlation_id, user_id=user_id, step_key=step_key, variant=variant)

    def record_variant_chosen(self, *, decision_id: str, correlation_id: str, user_id: str, step_key: str, variant: str) -> Any:
        return self._record_variant("variant_chosen", decision_id=decision_id, correlation_id=correlation_id, user_id=user_id, step_key=step_key, variant=variant)
