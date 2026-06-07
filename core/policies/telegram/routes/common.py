from __future__ import annotations

from collections.abc import Callable

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction

PM = Callable[..., ProposedAction]
