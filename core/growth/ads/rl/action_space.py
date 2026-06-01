from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Iterable, List, Sequence, Tuple

from .contracts import AdsRLAction, AdsRLOptSpec


@dataclass(frozen=True)
class ActionSpaceStats:
    n_actions: int
    truncated: bool = False


def build_action_space(spec: AdsRLOptSpec, *, max_actions: int = 5000) -> tuple[list[AdsRLAction], ActionSpaceStats]:
    """Expand finite action space.

    Safety:
    - hard-caps the cartesian product size to prevent accidental explosions.
    - truncation is deterministic: we keep the earliest actions.
    """
    budgets = [float(x) for x in (spec.daily_budgets or []) if x is not None]
    bids = [float(x) for x in (spec.bid_caps or []) if x is not None]
    cpas = [float(x) for x in (spec.cpa_targets or []) if x is not None]
    creatives = [str(x) for x in (spec.creatives or []) if str(x)]
    audiences = [str(x) for x in (spec.audiences or []) if str(x)]
    objectives = [str(x) for x in (spec.objectives or []) if str(x)]

    # Ensure at least one value per dimension: use None to mean "don't change".
    if not budgets:
        budgets = [None]  # type: ignore[list-item]
    if not bids:
        bids = [None]  # type: ignore[list-item]
    if not cpas:
        cpas = [None]  # type: ignore[list-item]
    if not creatives:
        creatives = [None]  # type: ignore[list-item]
    if not audiences:
        audiences = [None]  # type: ignore[list-item]
    if not objectives:
        objectives = [None]  # type: ignore[list-item]

    actions: list[AdsRLAction] = []
    truncated = False
    for daily_budget, bid_cap, cpa_target, creative_id, audience_id, objective in product(
        budgets, bids, cpas, creatives, audiences, objectives
    ):
        actions.append(
            AdsRLAction(
                campaign_id=str(spec.campaign_id),
                daily_budget=(float(daily_budget) if daily_budget is not None else None),
                bid_cap=(float(bid_cap) if bid_cap is not None else None),
                cpa_target=(float(cpa_target) if cpa_target is not None else None),
                creative_id=(str(creative_id) if creative_id is not None else None),
                audience_id=(str(audience_id) if audience_id is not None else None),
                objective=(str(objective) if objective is not None else None),
            )
        )
        if len(actions) >= int(max_actions):
            truncated = True
            break

    return actions, ActionSpaceStats(n_actions=len(actions), truncated=truncated)
