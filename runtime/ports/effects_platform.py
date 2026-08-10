from __future__ import annotations

from typing import Any, Protocol


class EffectsPlatformPort(Protocol):
    def generate_visual_creative(self, *, decision_id: str, correlation_id: str, tenant_id: str, user_id: str, kind: str, prompt: str, country_code: str = "", preferred_provider: str = "", aspect_ratio: str = "1:1", duration_seconds: int = 5, negative_prompt: str = "", reference_url: str = "", brand_context: str = "", wait_seconds: int = 0) -> Any: ...
    def poll_visual_creative(self, *, decision_id: str, correlation_id: str, tenant_id: str, user_id: str, job_id: str) -> Any: ...

    def enqueue_evolution_job(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        tenant_id: str,
        user_id: str,
        job_kind: str,
        payload: dict[str, Any] | None = None,
        channel: str = "telegram",
        channel_policy: dict[str, Any] | None = None,
    ) -> Any: ...

    def suggest_offer_patch(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        tenant_id: str,
        product: str,
        env: str,
        offer_id: str,
        action: str,
        notify_user_id: str | None = None,
        callback_query_id: str | None = None,
        channel: str = "telegram",
        channel_policy: dict[str, Any] | None = None,
    ) -> Any: ...

    def apply_offer_patch(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        tenant_id: str,
        product: str,
        env: str,
        offer_id: str,
        patch: dict[str, Any],
        mode: str = "dry_run",
        notify_user_id: str | None = None,
        callback_query_id: str | None = None,
        channel: str = "telegram",
        channel_policy: dict[str, Any] | None = None,
    ) -> Any: ...


__all__ = ["EffectsPlatformPort"]
