"""Reviewed creative-winner preview/apply gate (port of donor creative_winner).

Pure: recomputes ``yandex_growth.creative_allocation`` over the trial's arms, fingerprints the
exact evidence + policy, and on explicit confirmation returns one local traffic-plan fact only if
the reviewed revision and fingerprint still match. Never touches provider budgets or spend.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from application.business_flows import yandex_growth as yg

CANON_CREATIVE_WINNER = True


class CreativeWinnerApplyError(RuntimeError):
    """A reviewed optimization can no longer be applied safely."""


def fingerprint(*, trial_id: str, revision: int, date_from: str, date_to: str, arms: list[dict[str, Any]],
                rec: dict[str, Any], min_leads_per_arm: int, exploration_floor_bps: int, max_shift_bps: int) -> str:
    metric = str(rec["metric"])
    succ = {str(a["variant_id"]): int(a[metric]) for a in arms}
    payload = {
        "trial_id": trial_id, "revision": int(revision), "date_from": date_from, "date_to": date_to,
        "metric": metric, "status": rec["status"], "winner_variant_id": rec.get("winner_variant_id") or "",
        "variants": [{"variant_id": str(a["variant_id"]), "publication_job_id": str(a.get("publication_job_id") or ""),
                      "scope": str(a.get("scope", "variant")), "leads": int(a["leads"]),
                      "bookings": int(a["bookings"]), "won": int(a["won"])} for a in arms],
        "evidence": [{"variant_id": e["variant_id"], "publication_job_id": e["publication_job_id"],
                      "leads": e["leads"], "successes": succ.get(str(e["variant_id"]), 0),
                      "current_allocation_bps": e["current_allocation_bps"],
                      "proposed_allocation_bps": e["proposed_allocation_bps"]} for e in rec.get("evidence") or []],
        "policy": {"min_leads_per_arm": int(min_leads_per_arm), "exploration_floor_bps": int(exploration_floor_bps),
                   "max_shift_bps": int(max_shift_bps)},
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def preview(trial: dict[str, Any], *, metric: str = "bookings", min_leads_per_arm: int = 30,
            exploration_floor_bps: int = 1_000, max_shift_bps: int = 1_000) -> dict[str, Any]:
    """trial: {trial_id, revision, running, date_from, date_to, arms:[creative_allocation arm]}."""
    arms = list(trial["arms"])
    rec = yg.creative_allocation(arms, running=bool(trial.get("running")), metric=metric,
                                 min_leads_per_arm=min_leads_per_arm,
                                 exploration_floor_bps=exploration_floor_bps, max_shift_bps=max_shift_bps)
    fp = fingerprint(trial_id=str(trial["trial_id"]), revision=int(trial["revision"]),
                     date_from=str(trial["date_from"]), date_to=str(trial["date_to"]), arms=arms, rec=rec,
                     min_leads_per_arm=min_leads_per_arm, exploration_floor_bps=exploration_floor_bps,
                     max_shift_bps=max_shift_bps)
    return {"trial_id": str(trial["trial_id"]), "revision": int(trial["revision"]), "recommendation": rec,
            "fingerprint": fp, "date_from": str(trial["date_from"]), "date_to": str(trial["date_to"])}


def apply(trial: dict[str, Any], *, expected_revision: int, expected_fingerprint: str, confirmed: bool,
          **policy: Any) -> dict[str, Any]:
    """Recompute, verify reviewed identity, return the CAS plan-update fact (revision+1)."""
    if confirmed is not True:
        raise CreativeWinnerApplyError("creative winner requires explicit confirmation")
    pv = preview(trial, **policy)
    if int(expected_revision) != pv["revision"]:
        raise CreativeWinnerApplyError("creative winner recommendation is stale")
    if not hmac.compare_digest(str(expected_fingerprint or ""), pv["fingerprint"]):
        raise CreativeWinnerApplyError("creative winner evidence changed")
    rec = pv["recommendation"]
    if rec["status"] != "ready":
        raise CreativeWinnerApplyError("creative winner recommendation is not actionable")
    return {"step": "creative_plan_applied", "trial_id": pv["trial_id"], "expected_revision": pv["revision"],
            "revision": pv["revision"] + 1, "winner_variant_id": rec["winner_variant_id"],
            "allocations": [[str(j), int(b)] for j, b in rec["allocations"]], "fingerprint": pv["fingerprint"]}


__all__ = ["CANON_CREATIVE_WINNER", "CreativeWinnerApplyError", "apply", "fingerprint", "preview"]
