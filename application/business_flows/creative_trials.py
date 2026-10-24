"""Creative trial store (port of donor creative_winner list/page/reference over creative_growth_trials).

Pure projection over ``creative_trials@v1`` facts (``trial_recorded`` / ``trial_updated``); the
trial dicts are the shape ``creative_winner.preview/apply`` already consume. Read-only: viewers
are the promotion viewer roles; nothing here launches or spends on ads.
"""

from __future__ import annotations

from typing import Any

from application.business_flows.cockpit_growth_analytics import require_viewer

EVENT_TYPE = "creative_trials@v1"
_HEX = frozenset("0123456789abcdef-")


def replay(payloads: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    trials: dict[str, dict[str, Any]] = {}
    for p in payloads:
        tid, step = str(p.get("trial_id") or "").lower(), p.get("step")
        if not tid:
            continue
        if step == "trial_recorded" and tid not in trials:
            trials[tid] = {**dict(p.get("trial") or {}), "trial_id": tid, "updated_ms": int(p.get("at_ms") or 0)}
        elif step == "trial_updated" and tid in trials:
            trials[tid] = {
                **trials[tid],
                **dict(p.get("changes") or {}),
                "trial_id": tid,
                "updated_ms": int(p.get("at_ms") or 0),
            }
    return trials


def list_trials(trials: dict[str, dict[str, Any]], *, role: str) -> tuple[dict[str, Any], ...]:
    require_viewer(role)
    return tuple(sorted(trials.values(), key=lambda t: (-int(t["updated_ms"]), t["trial_id"])))


def list_page(
    trials: dict[str, dict[str, Any]], *, role: str, limit: int = 10, offset: int = 0
) -> tuple[tuple[dict[str, Any], ...], bool]:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
        raise ValueError("limit must be an integer between 1 and 50")
    if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= 10_000:
        raise ValueError("offset must be an integer between 0 and 10000")
    rows = list_trials(trials, role=role)
    return rows[offset : offset + limit], len(rows) > offset + limit


def resolve_reference(trials: dict[str, dict[str, Any]], *, role: str, reference: str) -> str:
    require_viewer(role)
    raw = str(reference or "").strip().lower()
    if len(raw) < 6 or any(c not in _HEX for c in raw):
        raise ValueError("creative trial reference is invalid")
    hits = sorted(t for t in trials if t.startswith(raw))
    if len(hits) != 1:
        raise ValueError("creative trial reference is stale or ambiguous")
    return hits[0]


def record(arg: str, *, now_ms: int) -> dict[str, Any]:
    """Owner-entered trial (no provider metrics feed): ``с|по|вариант:job:bps:лиды:записи:продажи;...``."""
    import hashlib

    parts = [p.strip() for p in str(arg or "").split("|")]
    if len(parts) != 3 or not all(parts):
        raise ValueError("формат: ГГГГ-ММ-ДД|ГГГГ-ММ-ДД|вариант:job:bps:лиды:записи:продажи;...")
    keys = ("variant_id", "publication_job_id", "allocation_bps", "leads", "bookings", "won")
    arms = []
    for a in (x.strip() for x in parts[2].split(";") if x.strip()):
        v = [x.strip() for x in a.split(":")]
        if len(v) != 6 or not all(x.isdigit() for x in v[2:]):
            raise ValueError("формат варианта: вариант:job:bps:лиды:записи:продажи")
        arms.append({k: (x if i < 2 else int(x)) for i, (k, x) in enumerate(zip(keys, v, strict=True))})
    if not 2 <= len(arms) <= 10:
        raise ValueError("нужно от 2 до 10 вариантов")
    raw = "|".join(parts).encode()
    tid = hashlib.sha256(raw).hexdigest()[:8] + "-" + hashlib.sha256(raw[::-1]).hexdigest()[:4]
    trial = {"revision": 1, "running": True, "date_from": parts[0], "date_to": parts[1], "arms": arms}
    return {"step": "trial_recorded", "trial_id": tid, "trial": trial, "at_ms": int(now_ms)}


def applied(plan: dict[str, Any], trial: dict[str, Any], *, now_ms: int) -> dict[str, Any]:
    """creative_winner.apply plan -> CAS ``trial_updated`` (new revision + allocations)."""
    alloc = {str(j): int(b) for j, b in plan["allocations"]}
    arms = [{**a, "allocation_bps": alloc.get(str(a["variant_id"]), a["allocation_bps"])} for a in trial["arms"]]
    return {"step": "trial_updated", "trial_id": plan["trial_id"], "at_ms": int(now_ms),
            "changes": {"revision": plan["revision"], "arms": arms, "winner_variant_id": plan["winner_variant_id"]}}


__all__ = ["EVENT_TYPE", "applied", "list_page", "list_trials", "record", "replay", "resolve_reference"]
