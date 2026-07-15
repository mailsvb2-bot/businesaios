from __future__ import annotations

from typing import Any, Protocol


class EffectsPlatformPort(Protocol):
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
