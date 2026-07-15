from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import asdict
from typing import Any

from core.llm.contracts import LLMMessage, LLMRequest
from core.observability.silent import swallow

from .contracts import GrowthGoalV1, GrowthHypothesisV1, GrowthSignalV1


def generate_hypotheses(llm: Any, *, tenant_id: str, goal: GrowthGoalV1, signals: GrowthSignalV1, n: int = 8, model: str = "") -> tuple[GrowthHypothesisV1, ...]:
    try:
        req = _build_request(tenant_id=tenant_id, goal=goal, signals=signals, n=int(n), model=str(model or ""))
        resp = _generate_sync(llm, req)
        items = _parse_json_array(resp)
        out: list[GrowthHypothesisV1] = []
        now = int(time.time() * 1000)
        for it in items:
            h = _coerce_hypothesis(it, tenant_id=tenant_id, now_ms=now)
            if h:
                out.append(h)
        return tuple(out[: int(n)])
    except Exception:
        swallow(__name__, "core/growth/strategy/llm_generator.py")
        return ()


def _build_request(*, tenant_id: str, goal: GrowthGoalV1, signals: GrowthSignalV1, n: int, model: str) -> LLMRequest:
    sys = """You are an AI growth strategist for a small business autopilot.
Return ONLY valid JSON.

Output format:
[
  {
    "stage": "acquisition|activation|retention|referral|revenue",
    "channel": "organic|seo|content|referral|partnerships|email|sms|push|telegram|whatsapp|messenger|instagram|web_chat|api|line|wechat|kakaotalk|viber|slack|discord|meta_ads|google_ads|tiktok_ads|vk_ads|yandex_direct|other_paid",
    "title": "short",
    "mechanism": "why it works",
    "expected_impact": "e.g. +10% profit in 14 days",
    "effort": "low|medium|high",
    "risk": "low|medium|high",
    "metric": "profit_minor|revenue_minor|spend_minor|leads|retention_d7_pct|conversion_lead_to_purchase_pct",
    "horizon_days": 7-30,
    "action_hints": {"optional": "freeform"}
  }
]

Rules:
- Be concrete and testable.
- Prefer actions executable through supported messaging channels and Ads.
- Use signals.top_channels when available; Telegram is supported but not assumed.
- Avoid vague advice like "improve marketing".
- Do NOT include any text outside JSON.
"""

    user = {"tenant_id": str(tenant_id), "goal": asdict(goal), "signals": asdict(signals), "n": int(n)}
    return LLMRequest(
        messages=[LLMMessage(role="system", content=sys), LLMMessage(role="user", content=json.dumps(user, ensure_ascii=False))],
        model=str(model or "gpt-4.1-mini"),
        temperature=0.35,
        max_tokens=900,
        timeout_s=25.0,
        metadata={"tenant_id": str(tenant_id), "use": "growth_strategy"},
    )


def _generate_sync(llm: Any, req: LLMRequest) -> str:
    fn = getattr(llm, "generate_sync", None)
    if callable(fn):
        return str(fn(req).content or "")

    import asyncio

    async def _go():
        r = await llm.generate(req)  # type: ignore[attr-defined]
        return r.content

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        raise RuntimeError("llm_sync_bridge_missing_in_running_loop")

    from core.marketing.async_runner import run_awaitable_sync
    return str(run_awaitable_sync(_go()) or "")


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def _parse_json_array(text: str) -> list[dict[str, Any]]:
    raw = (text or "").strip()
    m = _JSON_FENCE_RE.search(raw)
    if m:
        raw = (m.group(1) or "").strip()
    try:
        obj = json.loads(raw)
    except Exception:
        a = raw.find("[")
        b = raw.rfind("]")
        if a >= 0 and b >= 0 and b > a:
            obj = json.loads(raw[a : b + 1])
        else:
            raise

    if isinstance(obj, dict) and isinstance(obj.get("items"), list):
        obj = obj["items"]
    if not isinstance(obj, list):
        raise ValueError("llm_output_not_array")
    out: list[dict[str, Any]] = []
    for it in obj:
        if isinstance(it, dict):
            out.append(dict(it))
    return out


def _coerce_hypothesis(d: dict[str, Any], *, tenant_id: str, now_ms: int) -> GrowthHypothesisV1 | None:
    try:
        stage = str(d.get("stage") or "acquisition").strip().lower()
        channel = str(d.get("channel") or "organic").strip().lower()
        title = str(d.get("title") or "").strip()
        if not title:
            return None
        return GrowthHypothesisV1(
            hypothesis_id=str(uuid.uuid4()),
            created_ms=int(now_ms),
            tenant_id=str(tenant_id),
            stage=stage,  # type: ignore[arg-type]
            channel=channel,  # type: ignore[arg-type]
            title=title[:120],
            mechanism=str(d.get("mechanism") or "").strip()[:600],
            expected_impact=str(d.get("expected_impact") or "").strip()[:200],
            effort=str(d.get("effort") or "medium").strip().lower(),  # type: ignore[arg-type]
            risk=str(d.get("risk") or "medium").strip().lower(),  # type: ignore[arg-type]
            metric=str(d.get("metric") or "profit_minor").strip()[:60],
            horizon_days=int(d.get("horizon_days") or 14),
            action_hints=dict(d.get("action_hints") or {}),
        )
    except Exception:
        return None
