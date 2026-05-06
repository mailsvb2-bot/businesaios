from __future__ import annotations

import logging
from typing import Optional

from core.autopilot.stop_loss import StopLossState
from core.observability.throttled_logger import exception_throttled
from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction
from core.policies.telegram.handlers.autopilot_parts.shared import get_session
from core.policies.telegram.handlers.autopilot_parts.menu_and_dashboards import handle_menu_or_dashboard
from core.policies.telegram.handlers.autopilot_parts.flow import handle_flow

logger = logging.getLogger(__name__)


def handle_autopilot(ctx: TelegramCtx, *, user_id: str, default_price_rub: int) -> Optional[ProposedAction]:
    """Telegram Autopilot handler.

    The original all-in-one handler was split into small dispatch helpers:
    - menu_and_dashboards.py
    - flow.py
    - shared.py

    Invariants preserved:
    - no second brain: decisions still go through DecisionCore/runtime
    - one execution contract: execute_plan@v1 for composite actions
    - one data flow: state -> proposal -> runtime effects/events
    """
    try:
        sess = get_session(ctx, logger)
    except Exception:
        exception_throttled(logger, key=f"autopilot.session_read|{user_id}", msg="telegram_autopilot: failed to initialize session")
        sess = {}
    sl = StopLossState.from_settings(ctx.settings if isinstance(ctx.settings, dict) else {})

    action = handle_menu_or_dashboard(ctx, user_id=str(user_id), sess=sess, sl=sl, logger=logger)
    if action is not None:
        return action

    return handle_flow(ctx, user_id=str(user_id), default_price_rub=int(default_price_rub), sess=sess, sl=sl, logger=logger)