from __future__ import annotations

from typing import Any, Dict, Optional

from runtime._internal.effects_domains.admin_state_support import (
    apply_pricing_change_effect,
    emit_toggle_event,
    perform_admin_toggle,
    reject_pricing_change_effect,
    request_pricing_change_effect,
    send_optional_notification,
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
        plan_id: int,
        new_price: int,
        pricing_version: str,
        request_id: str | None = None,
        requested_by: str | None = None,
        reason: str | None = None,
    ) -> Any:
        """Apply governed pricing change. I/O delegated to admin_pricing."""
        assert_called_from_executor()
        return apply_pricing_change_effect(
            self,
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            admin_id=str(admin_id),
            plan_id=int(plan_id),
            new_price=int(new_price),
            pricing_version=str(pricing_version),
            request_id=request_id,
            requested_by=requested_by,
            reason=reason,
        )


    def request_pricing_change(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        admin_id: str,
        plan_id: int,
        new_price: int,
        request_id: str,
        suggested_pricing_version: str | None = None,
        reason: str | None = None,
    ) -> Any:
        """Create a pricing change request (no side-effects)."""
        assert_called_from_executor()
        return request_pricing_change_effect(
            self,
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            admin_id=str(admin_id),
            plan_id=int(plan_id),
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
        request_id: str,
        reason: str | None = None,
    ) -> Any:
        assert_called_from_executor()
        return reject_pricing_change_effect(
            self,
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            admin_id=str(admin_id),
            request_id=str(request_id),
            reason=reason,
        )
