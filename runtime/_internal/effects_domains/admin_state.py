from __future__ import annotations

from typing import Any

from runtime._internal.effects_domains.admin_pricing_requests import (
    assert_pricing_request_id_available,
    assert_pricing_request_open,
    resolve_pricing_change_request,
    validate_pricing_apply_against_request,
)
from runtime._internal.effects_domains.admin_state_support import (
    apply_pricing_change_effect,
    perform_admin_toggle,
    reject_pricing_change_effect,
    request_pricing_change_effect,
)
from runtime.security.runtime_asserts import assert_called_from_executor


class AdminStateEffectsMixin:
    """Admin/team state effects (roles/perms/user cards)."""

    event_log: Any

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
        notify_text: str | None = None,
        notify_reply_markup: dict[str, Any] | None = None,
        callback_query_id: str | None = None,
        channel: str = "telegram",
    ) -> Any:
        assert_called_from_executor()
        return perform_admin_toggle(
            self,
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            tenant_id=str(tenant_id),
            admin_id=str(admin_id),
            target_user_id=str(target_user_id),
            field_name="role",
            field_value=str(role),
            enabled=bool(enabled),
            notify_text=notify_text,
            notify_reply_markup=notify_reply_markup,
            callback_query_id=callback_query_id,
            channel=channel,
            event_log=self.event_log,
        )

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
        notify_text: str | None = None,
        notify_reply_markup: dict[str, Any] | None = None,
        callback_query_id: str | None = None,
        channel: str = "telegram",
    ) -> Any:
        assert_called_from_executor()
        return perform_admin_toggle(
            self,
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            tenant_id=str(tenant_id),
            admin_id=str(admin_id),
            target_user_id=str(target_user_id),
            field_name="perm",
            field_value=str(perm),
            enabled=bool(enabled),
            notify_text=notify_text,
            notify_reply_markup=notify_reply_markup,
            callback_query_id=callback_query_id,
            channel=channel,
            event_log=self.event_log,
        )

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
    ) -> Any:
        """Apply a governed price change to one tenant/product offer catalog."""
        assert_called_from_executor()

        effective_requested_by = requested_by
        normalized_request_id = str(request_id or "").strip()
        if normalized_request_id:
            request = validate_pricing_apply_against_request(
                self.event_log,
                tenant_id=str(tenant_id),
                request_id=normalized_request_id,
                product_id=str(product_id),
                environment=environment,
                offer_id=offer_id,
                plan_id=plan_id,
                new_price=int(new_price),
                pricing_version=str(pricing_version),
            )
            if requested_by and str(requested_by).strip() != request.requested_by:
                raise RuntimeError(
                    f"PRICING_CHANGE_REQUESTER_MISMATCH:{normalized_request_id}"
                )
            effective_requested_by = request.requested_by

        return apply_pricing_change_effect(
            self,
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            admin_id=str(admin_id),
            tenant_id=str(tenant_id),
            product_id=str(product_id),
            environment=environment,
            offer_id=offer_id,
            plan_id=plan_id,
            new_price=int(new_price),
            pricing_version=str(pricing_version),
            request_id=normalized_request_id or None,
            requested_by=effective_requested_by,
            reason=reason,
        )

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
    ) -> Any:
        """Record a scoped pricing-change request without applying it."""
        assert_called_from_executor()
        assert_pricing_request_id_available(
            self.event_log,
            tenant_id=str(tenant_id),
            request_id=str(request_id),
        )
        return request_pricing_change_effect(
            self,
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            admin_id=str(admin_id),
            tenant_id=str(tenant_id),
            product_id=str(product_id),
            environment=environment,
            offer_id=offer_id,
            plan_id=plan_id,
            new_price=int(new_price),
            request_id=str(request_id),
            suggested_pricing_version=suggested_pricing_version,
            reason=reason,
        )

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
    ) -> Any:
        assert_called_from_executor()
        request = resolve_pricing_change_request(
            self.event_log,
            tenant_id=str(tenant_id),
            request_id=str(request_id),
        )
        assert_pricing_request_open(
            self.event_log,
            tenant_id=request.tenant_id,
            request_id=request.request_id,
        )
        if product_id and str(product_id).strip() != request.product_id:
            raise RuntimeError(
                f"PRICING_CHANGE_REQUEST_MISMATCH:{request.request_id}:product_id"
            )
        return reject_pricing_change_effect(
            self,
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            admin_id=str(admin_id),
            tenant_id=request.tenant_id,
            product_id=request.product_id,
            request_id=request.request_id,
            reason=reason,
        )
