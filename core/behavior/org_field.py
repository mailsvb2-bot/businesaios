from __future__ import annotations

"""B2B / organization-level aggregation for BusinesAIOS.

We treat an org/account as a *field* of role-states.
"""

import math
from dataclasses import dataclass

from core.behavior.dirac_behavior import Complex4, DiracBehaviorModel

ROLE_WEIGHTS: dict[str, float] = {
    "lead": 1.0,
    "user": 0.9,
    "champion": 1.1,
    "decision_maker": 1.2,
    "economic_buyer": 1.0,
    "procurement": 0.8,
    "security": 0.8,
    "legal": 0.7,
}


def _w(role: str) -> float:
    r = str(role or "lead").strip().lower() or "lead"
    return float(ROLE_WEIGHTS.get(r, 0.85))


@dataclass(frozen=True)
class OrgField:
    psi_by_role: dict[str, Complex4]
    anti_by_role: dict[str, float]

    @staticmethod
    def empty() -> OrgField:
        return OrgField(psi_by_role={}, anti_by_role={})


def aggregate_org_observables(*, model: DiracBehaviorModel, field: OrgField, now_ms: int) -> dict[str, float]:
    if not field.psi_by_role:
        return {
            "org_engagement": 0.0,
            "org_alignment": 0.0,
            "org_blocker_index": 0.0,
            "org_purchase_probability": 0.0,
        }

    re = [0.0, 0.0, 0.0, 0.0]
    im = [0.0, 0.0, 0.0, 0.0]
    anti_w = 0.0
    total_w = 0.0
    phases: dict[str, tuple[float, float, float, float]] = {}

    for role, psi in field.psi_by_role.items():
        w = _w(role)
        total_w += w
        anti_w += w * float(field.anti_by_role.get(role, 0.0))
        for i in range(4):
            re[i] += w * float(psi.re[i])
            im[i] += w * float(psi.im[i])
        phases[str(role)] = psi.phases()

    if total_w <= 1e-9:
        total_w = 1.0
    re = [x / total_w for x in re]
    im = [x / total_w for x in im]
    anti = max(0.0, min(1.0, anti_w / total_w))

    org_psi = Complex4(tuple(re), tuple(im)).renormalize(target_norm=1.0)
    org_obs = model.observables(psi=org_psi, anti=anti, now_ms=int(now_ms))

    roles = list(phases.keys())
    if len(roles) <= 1:
        alignment = float(org_obs.get("coherence", 0.0))
    else:
        comp_align = []
        for j in range(4):
            mx = sum(math.cos(phases[r][j]) for r in roles) / float(len(roles))
            my = sum(math.sin(phases[r][j]) for r in roles) / float(len(roles))
            comp_align.append(math.sqrt(mx * mx + my * my))
        alignment = max(0.0, min(1.0, float(sum(comp_align) / 4.0)))

    blocker = max(
        0.0,
        min(
            1.0,
            (1.0 - alignment) * 0.55 + anti * 0.35 + float(org_obs.get("hesitation_score", 0.0)) * 0.10,
        ),
    )

    return {
        "org_engagement": float(org_obs.get("engagement_score", 0.0)),
        "org_alignment": float(alignment),
        "org_blocker_index": float(blocker),
        "org_purchase_probability": float(org_obs.get("purchase_probability", 0.0)) * float(alignment),
    }
