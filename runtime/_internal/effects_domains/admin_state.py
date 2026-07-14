from __future__ import annotations

from typing import Any

from runtime._internal.effects_domains.admin_pricing_requests import (
    PricingRequestLifecycle,
    assert_pricing_approval_allowed,
    assert_pricing_rejection_allowed,
    assert_pricing_request_matches,
    build_pricing_request_payload,
    pricing_event_evidence,
    resolve_pricing_request_lifecycle,
)
from runtime._internal.effects_domains.admin_state_support import (
    apply_pricing_change_effect,
    perform_admin_toggle,
    reject_pricing_change_effect,
    request_pricing_change_effect,
)
from runtime._internal.effects_tenant import assert_event_log_tenant
from runtime.security.runtime_asserts import assert_called_from_executor


def _is_not_found_error(exc: RuntimeError) -> bool:
    return str(exc).startswith("PRICING_CHANGE_REQUEST_NOT_FOUND:")


def _request_submission_matches(
    lifecycle: PricingRequestLifecycle,
    *,
    admin_id: str,
    proposed_payload: dict[str, Any],
) -> bool:
    request = lifecycle.request
    expected = {
        "tenant_id": request.tenant_id,
        "product_id": request.product_id,
        "environment": request.environment,
        "offer_id": request.offer_id,
        "plan_id": request.plan_id,
        "new_price": request.new_price,
        "request_id": request.request_id,
        "suggested_pricing_version": request.suggested_pricing_version,
        "reason": request.reason,
    }
    return expected == dict(proposed_payload) and request.requested_by == str(admin_id).strip()


def _replayed_request_result(lifecycle: PricingRequestLifecycle) -> dict[str, Any]:
    return {
        "ok": True,
        "status": "verified",
        "replayed": True,
        "request": lifecycle.request_payload,
        "router_evidence": pricing_event_evidence(
            code="pricing_change_request_recorded",
            event=lifecycle.request_event,
            fallback_ref=(
                f"pricing-request:{lifecycle.request.tenant_id}:"
                f"{lifecycle.request.product_id}:{lifecycle.request_id}"
            ),
        ),
    }


def _replayed_apply_result(lifecycle: PricingRequestLifecycle) -> dict[str, Any]:
    event = lifecycle.applied_event
    if event is None:
        raise RuntimeError("PRICING_APPLIED_EVENT_REQUIRED")
    return {
        "ok": True,
        "status": "verified",
        "replayed": True,
        "result": dict(event.get("payload") or {}),
        "router_evidence": pricing_event_evidence(
            code="pricing_change_recorded",
            event=event,
            fallback_ref=f"pricing-apply:{lifecycle.request.tenant_id}:{lifecycle.request_id}",
        ),
    }


def _replayed_rejection_result(lifecycle: PricingRequestLifecycle) -> dict[str, Any]:
    event = lifecycle.rejected_event
    if event is None:
        raise RuntimeError("PRICING_REJECTION_EVENT_REQUIRED")
    return {
        "ok": True,
        "status": "verified",
        "replayed": True,
        "rejection": dict(event.get("payload") or {}),
        "router_evidence": pricing_event_evidence(
            code="pricing_change_rejection_recorded",
            event=event,
            fallback_ref=f"pricing-rejection:{lifecycle.request.tenant_id}:{lifecycle.request_id}",
        ),
    }


class AdminStateEffectsMixin:
    """Admin/team state effects (roles/perms/pricing governance)."""

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
        """Apply one governed price change or replay its durable proof."""

        assert_called_from_executor()
        tenant = assert_event_log_tenant(
            self.event_log,
            tenant_id=str(tenant_id),
            operation="apply_pricing_change",
        )
        effective_requested_by = str(requested_by or "").strip() or None
        normalized_request_id = str(request_id or "").strip()
        if normalized_request_id:
            lifecycle = resolve_pricing_request_lifecycle(
                self.event_log,
                tenant_id=tenant,
                request_id=normalized_request_id,
            )
            assert_pricing_request_matches(
                lifecycle,
                product_id=str(product_id),
                environment=environment,
                offer_id=offer_id,
                plan_id=plan_id,
                new_price=int(new_price),
                pricing_version=str(pricing_version),
            )
            if requested_by and str(requested_by).strip() != lifecycle.requested_by:
                raise RuntimeError(
                    f"PRICING_CHANGE_REQUESTER_MISMATCH:{normalized_request_id}"
                )
            if lifecycle.applied_event is not None:
                return _replayed_apply_result(lifecycle)
            assert_pricing_approval_allowed(
                lifecycle,
                admin_id=str(admin_id),
            )
            effective_requested_by = lifecycle.requested_by

        return apply_pricing_change_effect(
            self,
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            admin_id=str(admin_id),
            tenant_id=tenant,
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
        """Record an immutable request or replay the exact existing request."""

        assert_called_from_executor()
        tenant = assert_event_log_tenant(
            self.event_log,
            tenant_id=str(tenant_id),
            operation="request_pricing_change",
        )
        proposed = build_pricing_request_payload(
            tenant_id=tenant,
            product_id=str(product_id),
            environment=environment,
            offer_id=offer_id,
            plan_id=plan_id,
            new_price=int(new_price),
            request_id=str(request_id),
            suggested_pricing_version=suggested_pricing_version,
            reason=reason,
        )
        try:
            lifecycle = resolve_pricing_request_lifecycle(
                self.event_log,
                tenant_id=tenant,
                request_id=str(request_id),
            )
        except RuntimeError as exc:
            if not _is_not_found_error(exc):
                raise
        else:
            if not _request_submission_matches(
                lifecycle,
                admin_id=str(admin_id),
                proposed_payload=proposed,
            ):
                raise RuntimeError(
                    f"PRICING_REQUEST_SCOPE_MISMATCH:{lifecycle.request_id}"
                )
            return _replayed_request_result(lifecycle)

        return request_pricing_change_effect(
            self,
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            admin_id=str(admin_id),
            tenant_id=tenant,
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
        tenant = assert_event_log_tenant(
            self.event_log,
            tenant_id=str(tenant_id),
            operation="reject_pricing_change",
        )
        lifecycle = resolve_pricing_request_lifecycle(
            self.event_log,
            tenant_id=tenant,
            request_id=str(request_id),
        )
        if product_id and str(product_id).strip() != lifecycle.request.product_id:
            raise RuntimeError(
                f"PRICING_CHANGE_REQUEST_MISMATCH:{lifecycle.request_id}:product_id"
            )
        assert_pricing_rejection_allowed(lifecycle)
        if lifecycle.rejected_event is not None:
            event = lifecycle.rejected_event
            payload = dict(event.get("payload") or {})
            if (
                str(event.get("user_id") or "") != str(admin_id)
                or str(payload.get("reason") or "").strip()
                != str(reason or "").strip()
            ):
                raise RuntimeError(
                    f"PRICING_REQUEST_TERMINAL_CONFLICT:{lifecycle.request_id}"
                )
            return _replayed_rejection_result(lifecycle)

        return reject_pricing_change_effect(
            self,
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            admin_id=str(admin_id),
            tenant_id=tenant,
            product_id=lifecycle.request.product_id,
            request_id=lifecycle.request_id,
            reason=reason,
        )
