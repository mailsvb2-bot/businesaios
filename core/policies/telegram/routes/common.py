from __future__ import annotations

from typing import Callable, Dict

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction

PM = Callable[..., ProposedAction]
