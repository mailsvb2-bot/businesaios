from __future__ import annotations

from typing import Any

from runtime._internal.effects_clients.visual_gateway_client import visual_gateway_json
from runtime._internal.effects_domains.visual_creative_gateway import (
    assert_visual_creative_job_id,
    assert_visual_creative_scope,
    visual_creative_evidence,
    visual_creative_idempotency_key,
    visual_creative_job_payload,
)
from runtime._internal.effects_tenant import assert_event_log_tenant
from runtime.observability.error_handling import swallow
from runtime.security.runtime_asserts import assert_called_from_executor


def _marketing_copy_evidence(
    *,
    decision_id: str,
    tenant_id: str,
    admin_id: str,
    step_key: str,
) -> dict[str, Any]:
    return {
        "source": "ledger",
        "verified": True,
        "status": "verified",
        "code": "marketing_copy_recorded",
        "external_refs": [
            f"marketing-copy:{tenant_id}:{decision_id}:{admin_id}:{step_key}"
        ],
        "confidence": 1.0,
        "payload": {
            "tenant_id": str(tenant_id),
            "admin_id": str(admin_id),
            "step_key": str(step_key),
        },
    }


class MarketingEffectsMixin:
    """Marketing runtime hooks and governed copy storage."""

    event_log: Any
    http_transport: Any

    def set_marketing_copy(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        tenant_id: str,
        admin_id: str,
        step_key: str,
        variant_a: str,
        variant_b: str,
        notify_text: str | None = None,
        notify_reply_markup: dict[str, Any] | None = None,
        callback_query_id: str | None = None,
        channel: str = "telegram",
        channel_policy: dict[str, Any] | None = None,
    ) -> Any:
        assert_called_from_executor()
        tenant = assert_event_log_tenant(
            self.event_log,
            tenant_id=str(tenant_id),
            operation="set_marketing_copy",
        )

        if channel == "telegram" and isinstance(callback_query_id, str) and callback_query_id.strip():
            try:
                self._telegram_answer_callback(  # type: ignore[attr-defined]
                    callback_query_id.strip(),
                    user_id=str(admin_id),
                    decision_id=str(decision_id),
                    correlation_id=str(correlation_id),
                )
            except Exception:
                swallow(__name__, "marketing_copy.answer_callback")

        payload = {
            "tenant_id": tenant,
            "step_key": str(step_key),
            "variant_a": str(variant_a)[:2000],
            "variant_b": str(variant_b)[:2000],
        }
        self.event_log.emit(
            event_type="marketing_copy_set",
            source="marketing",
            user_id=str(admin_id),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload=payload,
        )
        evidence = _marketing_copy_evidence(
            decision_id=str(decision_id),
            tenant_id=tenant,
            admin_id=str(admin_id),
            step_key=str(step_key),
        )

        notification: Any = None
        if isinstance(notify_text, str) and notify_text.strip():
            try:
                notification = self.send_message(  # type: ignore[attr-defined]
                    decision_id=str(decision_id),
                    correlation_id=str(correlation_id),
                    tenant_id=tenant,
                    user_id=str(admin_id),
                    text=str(notify_text)[:3500],
                    reply_markup=notify_reply_markup if isinstance(notify_reply_markup, dict) else None,
                    callback_query_id=str(callback_query_id) if callback_query_id else None,
                    channel=str(channel),
                    channel_policy=(
                        dict(channel_policy)
                        if isinstance(channel_policy, dict)
                        else None
                    ),
                    priority="normal",
                    critical=False,
                )
            except Exception as exc:
                notification = {"ok": False, "error": exc.__class__.__name__}

        return {
            "ok": True,
            "status": "verified",
            "copy": payload,
            "notification": notification,
            "router_evidence": evidence,
        }

    def generate_visual_creative(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        tenant_id: str,
        user_id: str,
        kind: str,
        prompt: str,
        country_code: str = "",
        preferred_provider: str = "",
        aspect_ratio: str = "1:1",
        duration_seconds: int = 5,
        negative_prompt: str = "",
        reference_url: str = "",
        brand_context: str = "",
        wait_seconds: int = 0,
    ) -> dict[str, Any]:
        assert_called_from_executor()
        tenant = assert_event_log_tenant(
            self.event_log,
            tenant_id=str(tenant_id),
            operation="generate_visual_creative",
        )
        decision = str(decision_id or "").strip()
        correlation = str(correlation_id or "").strip()
        user = str(user_id or "").strip()
        visual_kind = str(kind or "").strip().lower()
        visual_prompt = str(prompt or "").strip()
        if not decision:
            raise RuntimeError("DECISION_ID_REQUIRED")
        if not correlation:
            raise RuntimeError("CORRELATION_ID_REQUIRED")
        if not user:
            raise RuntimeError("USER_ID_REQUIRED")
        if visual_kind not in {"image", "video"} or not visual_prompt:
            raise ValueError("valid visual kind and prompt are required")

        bounded_wait = max(0, min(int(wait_seconds or 0), 60))
        idem = visual_creative_idempotency_key(
            tenant_id=tenant,
            decision_id=decision,
            kind=visual_kind,
        )
        raw = visual_gateway_json(
            "POST",
            "/v1/creative/generations",
            {
                "kind": visual_kind,
                "prompt": visual_prompt,
                "country_code": str(country_code or ""),
                "preferred_provider": str(preferred_provider or ""),
                "aspect_ratio": str(aspect_ratio or "1:1"),
                "duration_seconds": max(2, min(int(duration_seconds or 5), 15)),
                "negative_prompt": str(negative_prompt or ""),
                "reference_url": str(reference_url or ""),
                "brand_context": str(brand_context or ""),
                "wait_seconds": bounded_wait,
                "scope_id": tenant,
                "idempotency_key": idem,
            },
            timeout_s=max(30, bounded_wait + 15),
            transport=self.http_transport,
        )
        job = visual_creative_job_payload(raw)
        assert_visual_creative_scope(tenant_id=tenant, job=job)
        self.event_log.emit(
            event_type=(
                "visual_creative_generated"
                if job["status"] == "succeeded"
                else "visual_creative_submitted"
            ),
            source="visual_creative",
            user_id=user,
            decision_id=decision,
            correlation_id=correlation,
            payload={**job, "tenant_id": tenant},
        )
        return {
            "ok": job["status"] != "failed",
            "job": job,
            "router_evidence": visual_creative_evidence(tenant_id=tenant, job=job),
        }

    def poll_visual_creative(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        tenant_id: str,
        user_id: str,
        job_id: str,
    ) -> dict[str, Any]:
        assert_called_from_executor()
        tenant = assert_event_log_tenant(
            self.event_log,
            tenant_id=str(tenant_id),
            operation="poll_visual_creative",
        )
        decision = str(decision_id or "").strip()
        correlation = str(correlation_id or "").strip()
        user = str(user_id or "").strip()
        token = str(job_id or "").strip()
        if not decision:
            raise RuntimeError("DECISION_ID_REQUIRED")
        if not correlation:
            raise RuntimeError("CORRELATION_ID_REQUIRED")
        if not user:
            raise RuntimeError("USER_ID_REQUIRED")
        if not token or len(token) > 128 or not all(ch.isalnum() or ch in "_-" for ch in token):
            raise ValueError("valid visual job id is required")

        job = visual_creative_job_payload(
            visual_gateway_json(
                "GET",
                f"/v1/creative/generations/{token}",
                {"scope_id": tenant},
                timeout_s=30,
                transport=self.http_transport,
            )
        )
        assert_visual_creative_scope(tenant_id=tenant, job=job)
        assert_visual_creative_job_id(expected_job_id=token, job=job)
        self.event_log.emit(
            event_type="visual_creative_polled",
            source="visual_creative",
            user_id=user,
            decision_id=decision,
            correlation_id=correlation,
            payload={**job, "tenant_id": tenant},
        )
        return {
            "ok": job["status"] != "failed",
            "job": job,
            "router_evidence": visual_creative_evidence(tenant_id=tenant, job=job),
        }

    def record_variant_shown(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        user_id: str,
        step_key: str,
        variant: str,
    ) -> Any:
        assert_called_from_executor()
        self.event_log.emit(
            event_type="variant_shown",
            source="marketing",
            user_id=str(user_id),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload={"step_key": str(step_key), "variant": str(variant)},
        )
        return {"ok": True}

    def record_variant_chosen(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        user_id: str,
        step_key: str,
        variant: str,
    ) -> Any:
        assert_called_from_executor()
        self.event_log.emit(
            event_type="variant_chosen",
            source="marketing",
            user_id=str(user_id),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload={"step_key": str(step_key), "variant": str(variant)},
        )
        return {"ok": True}
