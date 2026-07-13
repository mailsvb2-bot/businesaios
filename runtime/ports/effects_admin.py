from __future__ import annotations

from typing import Protocol

from runtime.ports.effects_types import Any, Dict, Optional


class EffectsAdminPort(Protocol):
    def set_user_setting(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        tenant_id: str,
        user_id: str,
        key: str,
        value: Any = None,
        notify_text: Optional[str] = None,
        notify_reply_markup: Optional[Dict[str, Any]] = None,
        callback_query_id: Optional[str] = None,
        channel: str = "telegram",
    ) -> Any: ...

    def admin_set_role(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        tenant_id: str,
        admin_id: str,
        target_user_id: str,
        role: str,
        enabled: bool,
        notify_text: Optional[str] = None,
        notify_reply_markup: Optional[Dict[str, Any]] = None,
        callback_query_id: Optional[str] = None,
        channel: str = "telegram",
    ) -> Any: ...

    def admin_set_perm(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        tenant_id: str,
        admin_id: str,
        target_user_id: str,
        perm: str,
        enabled: bool,
        notify_text: Optional[str] = None,
        notify_reply_markup: Optional[Dict[str, Any]] = None,
        callback_query_id: Optional[str] = None,
        channel: str = "telegram",
    ) -> Any: ...

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
        notify_text: Optional[str] = None,
        notify_reply_markup: Optional[Dict[str, Any]] = None,
        callback_query_id: Optional[str] = None,
        channel: str = "telegram",
    ) -> Any: ...

    def marketing_llm_complete(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        admin_id: str,
        system: str,
        user: str,
        model: str | None = None,
    ) -> Any: ...

    def apply_pricing_change(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        admin_id: str,
        tenant_id: str,
        product_id: str,
        new_price: int,
        pricing_version: str,
        environment: str | None = None,
        offer_id: str | None = None,
        plan_id: int | None = None,
        request_id: str | None = None,
        requested_by: str | None = None,
        reason: str | None = None,
    ) -> Any: ...

    def request_pricing_change(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        admin_id: str,
        tenant_id: str,
        product_id: str,
        new_price: int,
        request_id: str,
        environment: str | None = None,
        offer_id: str | None = None,
        plan_id: int | None = None,
        suggested_pricing_version: str | None = None,
        reason: str | None = None,
    ) -> Any: ...

    def reject_pricing_change(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        admin_id: str,
        tenant_id: str,
        request_id: str,
        product_id: str | None = None,
        reason: str | None = None,
    ) -> Any: ...
