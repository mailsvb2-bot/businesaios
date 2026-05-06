from __future__ import annotations
"""Thin routing shim for ads apply flow callbacks.

Previously this module duplicated preview/confirm/cancel logic that also
lived in ads_apply.py, creating a divergence risk.

Now: single canon is ads_apply.handle_ads_apply().
This module is a thin wrapper so router.py's import/call stays unchanged.
"""

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.handlers.ads_apply import handle_ads_apply
from core.policies.telegram.helpers import ProposedAction
from core.ux.callbacks import CB_ADS_APPLY_CANCEL, CB_ADS_APPLY_CONFIRM, CB_ADS_APPLY_PREVIEW


def handle_ads_apply_flow(ctx: TelegramCtx, *, user_id: str) -> ProposedAction | None:
    """Route ads-apply callbacks to the canonical handler.

    Returns None if the callback doesn't belong to the ads-apply flow,
    so the router can fall through to other handlers.
    """
    cb = str(ctx.callback_data or "")
    if cb not in {CB_ADS_APPLY_PREVIEW, CB_ADS_APPLY_CONFIRM, CB_ADS_APPLY_CANCEL}:
        return None
    # Note: strict single-path — only ads_apply.handle_ads_apply triggers runtime apply.
    return handle_ads_apply(ctx, user_id=user_id)

# canonical runtime action proposed by this flow: ads_apply_execute@v1
