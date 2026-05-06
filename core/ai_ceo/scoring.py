from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from core.ai_ceo.ledger import GrowthSnapshotV1, to_dict as snapshot_to_dict
from core.ai_ceo.contracts import CEOPlanStepV1
from core.simulation.service import score_step
from core.simulation.contracts import SimScore


def rank_steps(*, steps: List[CEOPlanStepV1], snapshot: GrowthSnapshotV1) -> List[Tuple[CEOPlanStepV1, SimScore]]:
    snap = snapshot_to_dict(snapshot)
    ranked: List[Tuple[CEOPlanStepV1, SimScore]] = []
    for s in list(steps or []):
        sc = score_step(action=str(s.action), payload=dict(s.payload or {}), snapshot=snap)
        ranked.append((s, sc))
    ranked.sort(key=lambda x: (float(x[1].score), float(x[1].confidence)), reverse=True)
    return ranked
