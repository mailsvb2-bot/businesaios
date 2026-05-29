from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from core.ai_ceo.contracts import CEOPlanStepV1
from core.ai_ceo.ledger import GrowthSnapshotV1
from core.ai_ceo.ledger import to_dict as snapshot_to_dict
from core.simulation.contracts import SimScore
from core.simulation.service import score_step


def rank_steps(*, steps: list[CEOPlanStepV1], snapshot: GrowthSnapshotV1) -> list[tuple[CEOPlanStepV1, SimScore]]:
    snap = snapshot_to_dict(snapshot)
    ranked: list[tuple[CEOPlanStepV1, SimScore]] = []
    for s in list(steps or []):
        sc = score_step(action=str(s.action), payload=dict(s.payload or {}), snapshot=snap)
        ranked.append((s, sc))
    ranked.sort(key=lambda x: (float(x[1].score), float(x[1].confidence)), reverse=True)
    return ranked
