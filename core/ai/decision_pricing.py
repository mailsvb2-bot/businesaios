from __future__ import annotations

import logging
from typing import Any

from application.decision_policy.pricing import (
    allowed_price_band as _allowed_price_band,
)
from application.decision_policy.pricing import (
    band_rank,
)
from application.decision_policy.pricing import (
    merge_price_constraints as _merge_price_constraints,
)

logger = logging.getLogger(__name__)
CANON_DECISION_PRICING_HELPERS = True


def allowed_price_band(state: Any) -> str:
    return _allowed_price_band(state=state, logger=logger)


def merge_price_constraints(*, base: dict | None, override: dict | None) -> dict:
    return _merge_price_constraints(base=base, override=override, logger=logger)


__all__ = [
    "CANON_DECISION_PRICING_HELPERS",
    "allowed_price_band",
    "band_rank",
    "merge_price_constraints",
]
