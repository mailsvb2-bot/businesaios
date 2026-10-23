"""Activity / commercial ladder: ordered offer steps unlocked by evidence.

Ported from clientplatform ``commercial_ladder``. Returns eligible next offers
only; it never sells, prices or sends - a step that requires human approval
stays a suggestion for the owner.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from application.business_flows.projection import stable_id

KINDS = {"diagnostic": "диагностика", "audit": "аудит", "implementation": "внедрение", "recurring": "сопровождение"}


@dataclass(frozen=True)
class Step:
    step_id: str
    position: int
    kind: str
    title: str
    min_score: float
    requires_approval: bool = True


def parse_step(arg: str, *, position: int) -> dict[str, Any]:
    """``kind | title | min_score(0..1) [| auto]``."""
    parts = [p.strip() for p in str(arg or "").split("|")]
    if len(parts) < 3 or parts[0].casefold() not in KINDS or not parts[1] or len(parts[1]) > 200:
        raise ValueError("ladder_format: /ladder_add diagnostic|audit|implementation|recurring | Название | 0.3")
    try:
        min_score = float(parts[2].replace(",", "."))
    except ValueError as exc:
        raise ValueError("ladder_min_score_invalid") from exc
    if not math.isfinite(min_score):
        raise ValueError("ladder_min_score_invalid")
    return {
        "step": "ladder_step_added",
        "step_id": stable_id("ladder", position, parts[1].casefold()),
        "position": position,
        "kind": parts[0].casefold(),
        "title": parts[1],
        "min_score": max(0.0, min(min_score, 1.0)),
        "requires_approval": not (len(parts) > 3 and parts[3].casefold() == "auto"),
    }


def replay(payloads: list[dict[str, Any]]) -> tuple[list[Step], set[tuple[str, str]]]:
    steps: dict[str, Step] = {}
    done: set[tuple[str, str]] = set()
    for p in payloads:
        if p.get("step") == "ladder_step_added":
            steps[str(p["step_id"])] = Step(
                str(p["step_id"]),
                int(p["position"]),
                str(p["kind"]),
                str(p["title"]),
                float(p["min_score"]),
                bool(p.get("requires_approval", True)),
            )
        elif p.get("step") == "ladder_step_completed":
            done.add((str(p.get("customer_id")), str(p.get("step_id"))))
    return sorted(steps.values(), key=lambda s: (s.position, s.step_id)), done


def candidates(steps: list[Step], *, evidence_score: float, completed: set[str] = frozenset()) -> list[Step]:
    score = float(evidence_score)
    if not math.isfinite(score):
        raise ValueError("evidence_score_invalid")
    score = max(0.0, min(score, 1.0))
    return [s for s in steps if s.step_id not in completed and score >= s.min_score]


__all__ = ["KINDS", "Step", "candidates", "parse_step", "replay"]
