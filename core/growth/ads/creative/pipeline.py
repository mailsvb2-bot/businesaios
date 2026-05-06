from __future__ import annotations

from dataclasses import dataclass

import hashlib
from typing import Any, Dict, List, Optional, Tuple

from core.llm.contracts import LLMClient, LLMMessage, LLMRequest
from core.llm.templated import TemplatedLLM

# Canonical integration points (avoid provider coupling / multiple truths).
from core.ads.ads_service import AdsPlan, AdsService
from core.llm.agent import LLMAgent, LLMTaskContext, TaskType

from .models import CreativeCandidate, CreativeSelection, CreativeGuardrails
from .guardrails import validate_creative
from .prompting import CreativeBrief, build_messages


def _stable_id(*parts: str) -> str:
    h = hashlib.sha256("||".join(parts).encode("utf-8")).hexdigest()
    return "cr_" + h[:16]


def _parse_llm_text(text: str) -> Tuple[str, str, str, str]:
    # Very forgiving parser:
    # try to extract lines prefixed by "Headline:" etc; else take first lines.
    headline = ""
    primary = ""
    desc = ""
    cta = "Learn More"
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for l in lines:
        low = l.lower()
        if low.startswith("headline"):
            headline = l.split(":", 1)[-1].strip()
        elif low.startswith("primary"):
            primary = l.split(":", 1)[-1].strip()
        elif low.startswith("description"):
            desc = l.split(":", 1)[-1].strip()
        elif low.startswith("cta"):
            cta = l.split(":", 1)[-1].strip()
    if not headline and lines:
        headline = lines[0][:60]
    if not primary:
        primary = " ".join(lines[1:3])[:200] if len(lines) > 1 else ""
    if not desc:
        desc = " ".join(lines[3:4])[:90] if len(lines) > 3 else ""
    if cta not in {"Learn More", "Sign Up", "Book Now"}:
        cta = "Learn More"
    return headline[:60], primary[:200], desc[:90], cta




def _extract_llm_text(response: Any) -> str:
    content = getattr(response, "content", None)
    if isinstance(content, str) and content.strip():
        return content
    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text
    return ""


def _response_generation_mode(response: Any) -> str:
    raw = getattr(response, "raw", None)
    if isinstance(raw, dict) and str(raw.get("mode") or "").strip().lower() == "templated":
        return "templated"
    text = _extract_llm_text(response)
    return "llm" if text.strip() else "templated"


def _complete_creative_prompt(*, llm: Any, brief: CreativeBrief):
    messages = build_messages(brief)
    generate_sync = getattr(llm, "generate_sync", None)
    if callable(generate_sync):
        req = LLMRequest(
            messages=[LLMMessage(role=str(m.role), content=str(m.content)) for m in messages],
            model="ads-creative-fallback",
            temperature=0.4,
            max_tokens=350,
            metadata={"surface": "ads_creative_generate"},
        )
        return generate_sync(req)

    complete = getattr(llm, "complete", None)
    if callable(complete):
        return complete(messages=messages, temperature=0.4, max_tokens=350)

    raise TypeError("creative_pipeline_requires_llm_generate_sync_or_complete")

def generate_candidates(
    *,
    offer_arm: str,
    business_type: str,
    offer_title: str,
    offer_details: str,
    city: str = "",
    llm: Optional[LLMClient] = None,
    n: int = 3,
    guardrails: Optional[CreativeGuardrails] = None,
) -> List[CreativeCandidate]:
    """
    Generate N creative candidates for an offer. Uses LLM if provided, else template fallback.
    """
    if n <= 0:
        return []
    if llm is None:
        llm = TemplatedLLM()
    g = guardrails or CreativeGuardrails()

    out: List[CreativeCandidate] = []
    for i in range(n):
        brief = CreativeBrief(
            business_type=business_type,
            offer_title=offer_title,
            offer_details=offer_details,
            city=city,
            tone="friendly",
            language="ru",
        )
        resp = _complete_creative_prompt(llm=llm, brief=brief)
        h, p, d, cta = _parse_llm_text(_extract_llm_text(resp))
        cid = _stable_id(offer_arm, h, p, d, str(i))
        cand = CreativeCandidate(
            creative_id=cid,
            offer_arm=offer_arm,
            headline=h,
            primary_text=p,
            description=d,
            cta=cta,
            meta={"gen": _response_generation_mode(resp)},
        )
        ok, _reason = validate_creative(cand, g)
        if ok:
            out.append(cand)

    # If everything filtered out, fall back to a very safe template
    if not out:
        h = (offer_title or business_type).strip()[:60] or "Специальное предложение"
        p = (offer_details or "Узнайте подробности и запишитесь на удобное время.").strip()[:200]
        cid = _stable_id(offer_arm, h, p, "fallback")
        out = [
            CreativeCandidate(
                creative_id=cid,
                offer_arm=offer_arm,
                headline=h,
                primary_text=p,
                description="Подробности внутри"[:90],
                cta="Learn More",
                meta={"gen": "fallback"},
            )
        ]
    return out


def _score_candidate(c: CreativeCandidate, *, base: float = 0.1) -> float:
    """
    Heuristic scoring (used only until enough bandit data exists).
    Score is NOT a model; safe, simple rules.
    """
    s = base
    # prefer shorter, clearer headlines
    if 10 <= len(c.headline) <= 45:
        s += 0.05
    # prefer having concrete action in text
    low = (c.primary_text + " " + c.description).lower()
    if any(w in low for w in ["запись", "консультац", "расчёт", "осмотр", "встреча"]):
        s += 0.05
    # avoid too many symbols
    if low.count("!") == 0:
        s += 0.02
    return s


def select_creative(
    *,
    candidates: List[CreativeCandidate],
    guardrails: Optional[CreativeGuardrails] = None,
) -> CreativeSelection:
    """
    Select a creative among candidates using heuristic score (bandit selection lives outside).
    This function is deterministic and safe.
    """
    g = guardrails or CreativeGuardrails()
    scores: Dict[str, float] = {}
    ok_any = False
    for c in candidates:
        ok, _ = validate_creative(c, g)
        if ok:
            ok_any = True
            scores[c.creative_id] = _score_candidate(c)
        else:
            scores[c.creative_id] = -1.0

    best = max(candidates, key=lambda cc: scores.get(cc.creative_id, -1.0))
    return CreativeSelection(selected=best, reason="heuristic_best", scores=scores, guardrails_ok=ok_any)


# ---------------------------------------------------------------------------
# Variant B: LLMAgent + AdsService facade (canonical entrypoints)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CreativePipelineConfig:
    max_variants: int = 5


class CreativePipeline:
    """Canonical creative pipeline.

    This pipeline is provider-agnostic and only uses:
      - LLMAgent (task presets)
      - AdsService (plan/apply/metrics)

    The legacy CreativeLLMPipeline above remains for backward compatibility,
    but new DecisionCore adapters should use this pipeline to avoid divergence.
    """

    def __init__(self, llm: LLMAgent, ads: AdsService, cfg: CreativePipelineConfig) -> None:
        self._llm = llm
        self._ads = ads
        self._cfg = cfg

    def generate_creatives(self, ctx: LLMTaskContext) -> Dict[str, Any]:
        res = self._llm.run_task(TaskType.ADS_CREATIVE_GENERATE, ctx)
        return {"text": res.text, "data": res.json, "meta": res.meta}

    def critique_creatives(self, ctx: LLMTaskContext) -> Dict[str, Any]:
        res = self._llm.run_task(TaskType.ADS_CREATIVE_CRITIQUE, ctx)
        return {"text": res.text, "data": res.json, "meta": res.meta}

    def build_ads_plan(self, ctx: LLMTaskContext) -> AdsPlan:
        res = self._llm.run_task(TaskType.ADS_PLAN_BUILD, ctx)
        spec = {
            "plan": res.json.get("plan", []),
            "inputs": {"business": ctx.business, "audience": ctx.audience, "offer": ctx.offer},
        }
        return self._ads.build_plan(ctx.tenant_id, spec)