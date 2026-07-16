"""Canonical runtime handlers facade.

The public module path stays stable for action-registry contracts, while the
actual implementations are split into small domain modules.
"""

from __future__ import annotations

from runtime.handler_impl.domains.admin_ops import (
    handle_admin_set_perm,
    handle_admin_set_role,
    handle_admin_user_card,
    handle_set_marketing_copy,
)
from runtime.handler_impl.domains.payment_ops import (
    handle_capture_payment,
    handle_create_payment_and_send_link,
    handle_deploy_policy,
    handle_grant_access,
    handle_reconcile_payment,
    handle_reconcile_payments,
    handle_rollback_policy,
)
from runtime.handler_impl.domains.pricing_ops import (
    handle_apply_pricing_change,
    handle_reject_pricing_change,
    handle_request_pricing_change,
    handle_select_tariff,
)
from runtime.handler_impl.domains.user_ops import (
    handle_answer_callback,
    handle_log_mood,
    handle_send_audio,
    handle_send_weather,
    handle_set_user_setting,
)

__all__ = [
    "handle_admin_set_perm",
    "handle_admin_set_role",
    "handle_admin_user_card",
    "handle_answer_callback",
    "handle_apply_pricing_change",
    "handle_capture_payment",
    "handle_create_payment_and_send_link",
    "handle_deploy_policy",
    "handle_grant_access",
    "handle_log_mood",
    "handle_reconcile_payment",
    "handle_reconcile_payments",
    "handle_reject_pricing_change",
    "handle_request_pricing_change",
    "handle_rollback_policy",
    "handle_select_tariff",
    "handle_send_audio",
    "handle_send_weather",
    "handle_set_marketing_copy",
    "handle_set_user_setting",
]
