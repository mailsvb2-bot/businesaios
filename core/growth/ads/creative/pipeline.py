from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from core.ads.ads_service import AdsPlan, AdsService
from core.llm.agent import LLMAgent, LLMTaskContext, TaskType
from core.llm.contracts import LLMClient, LLMMessage, LLMRequest
from core.llm.templated import TemplatedLLM

from .guardrails import validate_creative
from .models import CreativeCandidate, CreativeGuardrails, CreativeSelection
from .prompting import CreativeBrief, build_messages

_FIELD_NAMES = {"headline", "primary", "description", "cta"}
_CTA_VALUES = {
    "learn more": "Learn More",
    "sign up": "Sign Up",
    "book now": "Book Now",
}


def _stable_id(*parts: str) -> str:
    h = hashlib.sha256("||".join(parts).encode("utf-8")).hexdigest()
    return "cr_" + h[:16]


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _parse_labeled_line(line: str) -> tuple[str, str] | None:
    normalized = line.strip().lstrip("-*• ").strip()
    if len(normalized) > 2 and normalized[0].isdigit() and normalized[1] in ".)":
        normalized = normalized[2:].lstrip()
    for separator in (":", "—", "–", "=", "-"):
        label, found, value = normalized.partition(separator)
        if not found:
            continue
        key = label.strip().lower()
        if key in _FIELD_NAMES:
            return key, value.strip()
        return None
    return None


def _parse_llm_text(text: str) -> tuple[str, str, str, str]:
    headline = ""
    primary = ""
    desc = ""
    cta = "Learn More"
    unlabeled: list[str] = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        parsed = _parse_labeled_line(line)
        if parsed is None:
            unlabeled.append(line)
            continue
        key, value = parsed
        if key == "headline":
            headline = value
        elif key == "primary":
            primary = value
        elif key == "description":
            desc = value
        else:
            cta = value
    if not headline and unlabeled:
        headline = unlabeled[0][:60]
    if not primary:
        primary = " ".join(unlabeled[1:3])[:200] if len(unlabeled) > 1 else ""
    if not desc:
        desc = " ".join(unlabeled[3:4])[:90] if len(unlabeled) > 3 else ""
    cta = _CTA_VALUES.get(cta.strip().lower(), "Learn More")
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


def _has_required_copy(candidate: CreativeCandidate) -> bool:
    return bool(candidate.headline.strip() and candidate.primary_text.strip())


def _safe_fallback_candidate(
    *,
    offer_arm: str,
    business_type: str,
    offer_title: str,
    offer_details: str,
    guardrails: CreativeGuardrails,
) -> CreativeCandidate:
    headline = offer_title or business_type or "Специальное предложение"
    primary = offer_details or "Узнайте подробности и запишитесь на удобное время."
    candidate = CreativeCandidate(
        creative_id=_stable_id(offer_arm, headline[:60], primary[:200], "fallback"),
        offer_arm=offer_arm,
        headline=headline[:60],
        primary_text=primary[:200],
        description="Подробности внутри",
        cta="Learn More",
        meta={"gen": "fallback"},
    )
    if validate_creative(candidate, guardrails)[0]:
        return candidate
    headline = "Специальное предложение"
    primary = "Узнайте подробности и запишитесь на удобное время."
    return CreativeCandidate(
        creative_id=_stable_id(offer_arm, headline, primary, "fallback"),
        offer_arm=offer_arm,
        headline=headline,
        primary_text=primary,
        description="Подробности внутри",
        cta="Learn More",
        meta={"gen": "fallback"},
    )


def generate_candidates(
    *,
    offer_arm: str,
    business_type: str,
    offer_title: str,
    offer_details: str,
    city: str = "",
    llm: LLMClient | None = None,
    n: int = 3,
    guardrails: CreativeGuardrails | None = None,
) -> list[CreativeCandidate]:
    if n <= 0:
        return []
    if llm is None:
        llm = TemplatedLLM()
    g = guardrails or CreativeGuardrails()
    normalized_business_type = _clean_text(business_type)
    normalized_offer_title = _clean_text(offer_title)
    normalized_offer_details = _clean_text(offer_details)
    normalized_city = _clean_text(city)

    out: list[CreativeCandidate] = []
    for i in range(n):
        brief = CreativeBrief(
            business_type=normalized_business_type,
            offer_title=normalized_offer_title,
            offer_details=normalized_offer_details,
            city=normalized_city,
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
        if ok and _has_required_copy(cand):
            out.append(cand)

    if not out:
        out = [
            _safe_fallback_candidate(
                offer_arm=offer_arm,
                business_type=normalized_business_type,
                offer_title=normalized_offer_title,
                offer_details=normalized_offer_details,
                guardrails=g,
            )
        ]
    return out


def _score_candidate(c: CreativeCandidate, *, base: float = 0.1) -> float:
    s = base
    if 10 <= len(c.headline) <= 45:
        s += 0.05
    low = (c.primary_text + " " + c.description).lower()
    if any(w in low for w in ["запись", "консультац", "расчёт", "осмотр", "встреча"]):
        s += 0.05
    if low.count("!") == 0:
        s += 0.02
    return s


def select_creative(
    *,
    candidates: list[CreativeCandidate],
    guardrails: CreativeGuardrails | None = None,
) -> CreativeSelection:
    if not candidates:
        raise ValueError("creative_selection_requires_candidates")
    g = guardrails or CreativeGuardrails()
    scores: dict[str, float] = {}
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


@dataclass(frozen=True)
class CreativePipelineConfig:
    max_variants: int = 5


class CreativePipeline:
    """Canonical provider-neutral creative pipeline."""

    def __init__(self, llm: LLMAgent, ads: AdsService, cfg: CreativePipelineConfig) -> None:
        self._llm = llm
        self._ads = ads
        self._cfg = cfg

    def generate_creatives(self, ctx: LLMTaskContext) -> dict[str, Any]:
        res = self._llm.run_task(TaskType.ADS_CREATIVE_GENERATE, ctx)
        return {"text": res.text, "data": res.json, "meta": res.meta}

    def critique_creatives(self, ctx: LLMTaskContext) -> dict[str, Any]:
        res = self._llm.run_task(TaskType.ADS_CREATIVE_CRITIQUE, ctx)
        return {"text": res.text, "data": res.json, "meta": res.meta}

    def build_ads_plan(self, ctx: LLMTaskContext) -> AdsPlan:
        res = self._llm.run_task(TaskType.ADS_PLAN_BUILD, ctx)
        spec = {
            "plan": res.json.get("plan", []),
            "inputs": {"business": ctx.business, "audience": ctx.audience, "offer": ctx.offer},
        }
        return self._ads.build_plan(ctx.tenant_id, spec)
