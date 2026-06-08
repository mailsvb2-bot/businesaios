from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Any, Optional

from core.observability.silent import swallow


@dataclass(frozen=True)
class ProposedAction:
    """A small, explicit action proposal.

    DecisionCore will validate it via SchemaRegistry.
    """

    action: str
    payload: dict[str, Any]


def propose(action: str, payload: dict[str, Any] | None = None) -> ProposedAction:
    return ProposedAction(action=str(action), payload=dict(payload or {}))


def propose_message(
    *,
    user_id: str,
    text: str,
    reply_markup: dict | None = None,
    callback_query_id: str | None = None,
    track_event_type: str | None = None,
    track_payload: dict[str, Any] | None = None,
) -> ProposedAction:
    p: dict[str, Any] = {"user_id": str(user_id or "anonymous"), "text": str(text)}
    if isinstance(callback_query_id, str) and callback_query_id.strip():
        # UX: answerCallbackQuery to stop the spinning loader.
        # This is still a single action (send_message@v1); the transport may
        # perform an additional Telegram API call under the same sealed effect.
        p["callback_query_id"] = callback_query_id.strip()
    if isinstance(reply_markup, dict) and reply_markup:
        p["reply_markup"] = reply_markup
    if isinstance(track_event_type, str) and track_event_type.strip():
        p["track_event_type"] = str(track_event_type).strip()
        if isinstance(track_payload, dict) and track_payload:
            p["track_payload"] = dict(track_payload)
    return propose("send_message@v1", p)


def choose_marketing_variant(
    *,
    user_id: str,
    step_key: str,
    seed: str = "1",
    bandit: dict[str, dict[str, float]] | None = None,
) -> str:
    """Choose A/B for a step.

    Default behavior is legacy deterministic hashing.
    If bandit stats are provided, use deterministic Thompson sampling (Beta priors)
    seeded by sha256(seed|user_id|step_key) so retries remain stable.
    """
    base = f"{seed}|{user_id}|{step_key}".encode()
    h = hashlib.sha256(base).digest()

    fallback = "a" if (h[0] % 2 == 0) else "b"
    if not isinstance(bandit, dict):
        return fallback

    a = bandit.get("a") if isinstance(bandit.get("a"), dict) else None
    b = bandit.get("b") if isinstance(bandit.get("b"), dict) else None
    try:
        a_alpha = float((a or {}).get("alpha", 1.0))
        a_beta = float((a or {}).get("beta", 1.0))
        b_alpha = float((b or {}).get("alpha", 1.0))
        b_beta = float((b or {}).get("beta", 1.0))
        a_alpha = max(1e-6, a_alpha)
        a_beta = max(1e-6, a_beta)
        b_alpha = max(1e-6, b_alpha)
        b_beta = max(1e-6, b_beta)
    except Exception:
        return fallback

    seed_int = int.from_bytes(h[:8], "big", signed=False)
    rng = random.Random(seed_int)
    try:
        sa = rng.betavariate(a_alpha, a_beta)
        sb = rng.betavariate(b_alpha, b_beta)
        return "a" if sa >= sb else "b"
    except Exception:
        return fallback


def build_legacy_prices(*, default_price_rub: int) -> dict[str, int]:
    """Best-effort legacy title->price mapping.

    Source of truth is the plan catalog (data/plans.json). Hardcoding prices creates drift.
    """
    try:
        from core.plans import active_plans

        mp: dict[str, int] = {}
        for p in active_plans():
            try:
                title = str(p.get("title") or "").strip()
                price = int(p.get("price") or 0)
                if title and price > 0:
                    mp[title] = price
            except Exception:
                continue
        if mp:
            return mp
    except Exception:
        swallow(__name__, 'core/policies/telegram/helpers.py')
    return {"Полный доступ": int(default_price_rub)}
