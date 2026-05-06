from __future__ import annotations

"""Ads Apply flow codec.

This module is a small deterministic primitive:
- encodes a pending plan into settings-safe dict
- computes stable idempotency key material
"""

import hashlib
import json
from typing import Any, Dict, Mapping

PENDING_KEY = "ads:apply_pending_plan"


def normalize_plan(plan: Mapping[str, Any] | None) -> Dict[str, Any]:
    p = dict(plan or {})
    # Drop volatile keys.
    for k in ["created_ms", "nonce"]:
        p.pop(k, None)
    # Ensure canonical ordering in nested dicts by json roundtrip.
    try:
        raw = json.dumps(p, sort_keys=True, ensure_ascii=False)
        return json.loads(raw)
    except Exception:
        return p


def compute_plan_idempotency_key(plan: Mapping[str, Any] | None) -> str:
    p = normalize_plan(plan)
    raw = json.dumps(p, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def plan_summary_text(plan: Mapping[str, Any] | None) -> str:
    p = dict(plan or {})
    platform = str(p.get("platform") or "")
    daily = int(p.get("daily_budget_minor") or 0)
    ops = list(p.get("ops") or [])
    return (
        "🧾 План рекламных изменений\n\n"
        f"Платформа: {platform or '—'}\n"
        f"Дневной бюджет: {daily} minor\n"
        f"Операций: {len(ops)}\n"
        "\n"
        "Это *предпросмотр*. Нажми ‘Подтвердить’, чтобы применить (если разрешено)."
    )
