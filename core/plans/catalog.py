"""Tariff/plan catalog (PURE).

Etalon-5 uses a DB-driven plans table. In the canonical kernel we keep
the catalog as data (JSON) and treat it as immutable within runtime.
Admin editing can later be implemented as meta-decisions that update
this data source (out of scope here).

The policy layer reads the catalog; prices are re-checked at pay time.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.observability.silent import swallow


def _repo_root() -> Path:
    # this file: core/plans/catalog.py -> core -> repo root
    return Path(__file__).resolve().parents[2]


def _catalog_path() -> Path:
    return _repo_root() / "data" / "plans.json"


def load_plans() -> list[dict[str, Any]]:
    path = _catalog_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return [p for p in raw if isinstance(p, dict)]
    except Exception:
        swallow(__name__, 'core/plans/catalog.py')
    return []


def active_plans() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in load_plans():
        try:
            if not p.get("is_active", True):
                continue
            # Minimal validation
            plan_id = int(p.get("plan_id") or 0)
            price = int(p.get("price") or 0)
            title = str(p.get("title") or "").strip()
            scope = str(p.get("scope") or "").strip()
            days = int(p.get("days") or 0)
            plan_code = str(p.get("plan_code") or p.get("code") or "").strip()
            description = str(p.get("description") or "").strip()
            schedule = str(p.get("schedule") or "").strip()
            terms_short = str(p.get("terms_short") or "").strip()
            if plan_id <= 0 or price <= 0 or not title or not scope or days <= 0 or not plan_code:
                continue
            out.append({
                "plan_id": plan_id,
                "title": title,
                "scope": scope,
                "days": days,
                "price": price,
                "plan_code": plan_code,
                "description": description,
                "schedule": schedule,
                "terms_short": terms_short,
                "is_active": True,
            })
        except Exception:
            continue
    # stable order
    out.sort(key=lambda x: int(x.get("sort") or x.get("plan_id") or 0))
    return out


def plan_by_id(plan_id: int) -> dict[str, Any] | None:
    try:
        pid = int(plan_id)
    except Exception:
        return None
    for p in active_plans():
        if int(p.get("plan_id")) == pid:
            return p
    return None


def get_plan_by_id(plan_id: int) -> dict[str, Any] | None:
    """Return a single active plan by id (pure helper).

    Policy code should use this instead of duplicating catalog scanning logic.
    """
    plan = plan_by_id(int(plan_id))
    return dict(plan) if isinstance(plan, dict) else None
