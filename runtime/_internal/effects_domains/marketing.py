from __future__ import annotations

from typing import Any

from core.growth.ads.creative.prompting import render_pack_idempotency_key, scene_from_text, scene_key_elements

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
from runtime.platform.config.env_flags import env_bool, env_int
from runtime.security.runtime_asserts import assert_called_from_executor


def _marketing_copy_evidence(*, decision_id: str, tenant_id: str, admin_id: str, step_key: str) -> dict[str, Any]:
    return {"source": "ledger", "verified": True, "status": "verified", "code": "marketing_copy_recorded", "external_refs": [f"marketing-copy:{tenant_id}:{decision_id}:{admin_id}:{step_key}"], "confidence": 1.0, "payload": {"tenant_id": str(tenant_id), "admin_id": str(admin_id), "step_key": str(step_key)}}


def _visual_identity(*, decision_id: str, correlation_id: str, user_id: str) -> tuple[str, str, str]:
    values = tuple(str(value or "").strip() for value in (decision_id, correlation_id, user_id))
    for value, code in zip(values, ("DECISION_ID_REQUIRED", "CORRELATION_ID_REQUIRED", "USER_ID_REQUIRED"), strict=True):
        if not value:
            raise RuntimeError(code)
    return values  # type: ignore[return-value]


VIDEO_ENV = "BAI_VIDEO_GENERATION_ENABLED"  # video generation: off by default (dry run, no provider call)
VIDEO_PROVIDER_ALLOW = frozenset({"", "yandexart_motion"})  # Russian providers only; foreign ones are refused
AD_PROVIDER_ENV = "BAI_AD_SPEND_PROVIDER_ENABLED"  # provider reads (budget snapshot): off by default
AD_MUTATIONS_ENV = "BAI_AD_SPEND_MUTATIONS_ENABLED"  # launch / suspend / budget changes: off by default
AD_CEILING_ENV = "BAI_AD_SPEND_CEILING_MINOR"  # absolute per-authorization ceiling; unset = no spend (fail closed)
AD_READ_ACTIONS = frozenset({"read_budget", "minimum_weekly"})
AD_MUTATING_ACTIONS = frozenset({"configure_budget", "moderate_ad", "suspend_ad"})


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
        if visual_kind == "video":
            blocked = self._video_gate(decision, correlation, tenant, user, preferred_provider)
            if blocked is not None:
                return blocked
        owner_context = f"{visual_prompt} {brand_context}"
        if visual_direction is None and "before" in (scene := scene_from_text(visual_prompt)):
            visual_direction = scene
        if visual_direction is not None:
            visual_prompt = visual_direction_prompt(visual_direction, owner_context=owner_context)
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
            if visual_direction is not None and env_bool("VISUAL_SEMANTIC_RETRY", True):
                job = self._visual_quality_retry(job, payload, key, dict(visual_direction), owner_context, tenant, wait)
            if overlay and job["status"] == "succeeded":
                formats, composition = list(overlay.get("formats") or ["feed"]), {k: v for k, v in overlay.items() if k != "formats"}
                pack = visual_gateway_json("POST", "/v1/creative/render-packs", {"source_job_id": job["id"], "scope_id": tenant, "idempotency_key": render_pack_idempotency_key(key, composition, formats), "formats": formats, "composition": composition}, timeout_s=300, transport=self.http_transport)
                job["render_pack"] = {k: pack.get(k) for k in ("id", "status", "error_code")}
            jobs.append(job)
        event_type = "visual_creative_generated" if jobs[0]["status"] == "succeeded" else "visual_creative_submitted"
        result = self._visual_result(tenant=tenant, user=user, decision=decision, correlation=correlation, job=jobs[0], event_type=event_type)
        return {**result, "candidates": jobs} if variants > 1 else result

    def _video_gate(self, decision: str, correlation: str, tenant: str, user: str, provider: str) -> dict[str, Any] | None:
        """Video is OFF unless BAI_VIDEO_GENERATION_ENABLED=1 (dry run + event, no provider call); Russian providers only."""
        if str(provider or "").strip().lower() not in VIDEO_PROVIDER_ALLOW:
            raise PermissionError("video_provider_not_allowed")
        if env_bool(VIDEO_ENV, False):
            return None
        self.event_log.emit(event_type="video_dry_run", source="runtime_effects", user_id=user, decision_id=decision, correlation_id=correlation, payload={"tenant_id": tenant, "flag": VIDEO_ENV})
        return {"ok": True, "status": "dry_run", "kind": "video", "meta": {"mode": "dry_run", "flag": VIDEO_ENV}}

    def ad_provider_action(self, *, decision_id: str, correlation_id: str, tenant_id: str, user_id: str, action: str, params: dict[str, Any], idempotency_key: str = "") -> dict[str, Any]:
        """Executor-only ad provider access. Reads need BAI_AD_SPEND_PROVIDER_ENABLED, mutations also
        BAI_AD_SPEND_MUTATIONS_ENABLED; otherwise a dry run (event, no network). Real calls go through the
        injected ``ad_provider_transport`` only, with a mandatory idempotency key and a hard spend ceiling."""
        assert_called_from_executor()
        tenant = self._visual_tenant(tenant_id, "ad_provider_action")
        decision, correlation, user = _visual_identity(decision_id=decision_id, correlation_id=correlation_id, user_id=user_id)
        name, data, key = str(action or "").strip(), dict(params or {}), str(idempotency_key or "").strip()
        mutating = name in AD_MUTATING_ACTIONS
        if not mutating and name not in AD_READ_ACTIONS:
            raise ValueError("ad_provider_action_invalid")
        if mutating and not key:
            raise ValueError("ad_provider_idempotency_key_required")
        flags = [AD_PROVIDER_ENV] + ([AD_MUTATIONS_ENV] if mutating else [])
        base = {"tenant_id": tenant, "action": name, "idempotency_key": key}
        if not all(env_bool(flag, False) for flag in flags):
            self.event_log.emit(event_type="ad_provider_dry_run", source="runtime_effects", user_id=user, decision_id=decision, correlation_id=correlation, payload={**base, "flags": flags})
            return {"ok": True, "status": "dry_run", "action": name, "meta": {"mode": "dry_run", "flags": flags}}
        if name == "configure_budget":
            ceiling = env_int(AD_CEILING_ENV, 0)
            hard, daily = data.get("hard_cap_minor"), data.get("daily_cap_minor")
            if type(hard) is not int or type(daily) is not int or ceiling <= 0 or not 0 < daily <= hard <= ceiling:
                self.event_log.emit(event_type="ad_provider_refused", source="runtime_effects", user_id=user, decision_id=decision, correlation_id=correlation, payload={**base, "reason": "spend_ceiling"})
                return {"ok": False, "status": "refused", "error": "AD_SPEND_CEILING", "action": name}
        transport = getattr(self, "ad_provider_transport", None)
        if not callable(transport):
            self.event_log.emit(event_type="ad_provider_unconfigured", source="runtime_effects", user_id=user, decision_id=decision, correlation_id=correlation, payload=base)
            return {"ok": False, "status": "unconfigured", "error": "AD_PROVIDER_TRANSPORT_NOT_CONFIGURED", "action": name}
        out = dict(transport(action=name, params=data, idempotency_key=key, tenant_id=tenant) or {})
        self.event_log.emit(event_type="ad_provider_action", source="runtime_effects", user_id=user, decision_id=decision, correlation_id=correlation, payload={**base, "ok": bool(out.get("ok"))})
        return {"ok": bool(out.get("ok")), "status": str(out.get("status") or ("done" if out.get("ok") else "failed")), "action": name, "result": out}

    def _visual_quality_retry(self, job: dict[str, Any], payload: dict[str, Any], key: str, direction: dict[str, str], owner_context: str, tenant: str, wait: int) -> dict[str, Any]:
        """One bounded regeneration on provider failure or semantic QA review."""
        elements, missing = scene_key_elements(direction), []
        if job["status"] == "succeeded" and job["kind"] == "image":
            request = ("; ".join(f"видно: {item}" for item in elements) + ". " + payload["prompt"])[:1500]
            contract = {"version": 1, "kind": "image", "country_code": payload["country_code"], "owner_request": request, "semantic_flags": []}
            try:
                qa = visual_gateway_json("POST", f"/v1/creative/generations/{job['id']}/semantic-qa", {"scope_id": tenant, "contract": contract}, timeout_s=60, transport=self.http_transport)
            except Exception:
                qa = {"status": "unavailable"}
            job["semantic_qa"] = str(qa.get("status") or "unavailable") if isinstance(qa, dict) else "unavailable"
            if job["semantic_qa"] != "needs_review":
                return job
            issues = " ".join(str(item) for item in qa.get("issues") or ()).casefold()
            missing = [item for item in elements if item.casefold()[:12] in issues]
        elif job["status"] != "failed":
            return job
        emphasis = "; ".join(missing or elements)
        retry = {**payload, "idempotency_key": key + (":q1" if job["status"] == "succeeded" else ":r1"), "prompt": visual_direction_prompt(direction, owner_context=owner_context, emphasis=emphasis)}
        fresh = visual_creative_job_payload(visual_gateway_json("POST", "/v1/creative/generations", retry, timeout_s=max(30, wait + 15), transport=self.http_transport))
        assert_visual_creative_binding(tenant_id=tenant, job=fresh, expected_kind=job["kind"])
        return {**fresh, "retry_of": job["id"]}

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
