"""Sales AI copilot for a lead (port of ClientPlatform sales_ai_orchestration/policy, in-process).

Pure policy around one LLM call that the executor makes through the existing
``marketing_llm_complete`` transport. Hard limits kept from the donor:
* only Russian providers (YandexGPT / GigaChat) may receive customer text;
* the owner enables it (``/setting sales_ai = on``); ``sales_ai_mode`` = redacted (default) | standard | no_cloud;
* the model only *suggests*: conservative milestones (need / qualified) and a draft reply,
  stored as a ``lead_note``; nothing is sent to the customer and payment/loss are never inferred.
"""

from __future__ import annotations

import json
import re
from typing import Any

from application.business_flows import sales as sl
from core.llm.redaction import redact_text

CANON_SALES_AI = True
RUSSIAN_PROVIDERS = frozenset({"yandexgpt", "gigachat"})
MODES = ("redacted", "standard", "no_cloud")
MAX_TEXT = 2000
MAX_REPLY = 600
_HANDLE = re.compile(r"(?<!\w)@[A-Za-z0-9_]{5,32}\b")
_URL = re.compile(r"(?i)https?://\S+")
INTENTS = ("service_interest", "pricing", "booking", "question", "objection", "other")
SYSTEM = (
    "Вы помощник владельца малого бизнеса в переписке с клиентом. Ответьте строго JSON без пояснений: "
    '{"intent": один из ' + "|".join(INTENTS) + ', "need_is_specific": bool, "purchase_intent_explicit": bool, '
    '"purchase_readiness": 0..1, "confidence": 0..1, "explicit_human_request": bool, "sensitive_context": bool, '
    '"negative_sentiment": bool, "reply": "черновик ответа на русском, вежливо на Вы, без цен и ссылок"}'
)


def egress_permit(settings: dict[str, str], provider: str) -> str:
    """Donor sales_ai_analysis_egress_permit: returns data mode or raises PermissionError."""
    if settings.get("sales_ai", "off").strip().casefold() not in ("on", "1", "true"):
        raise PermissionError("ИИ-помощник продаж выключен: /setting sales_ai = on")
    if str(provider or "").strip().casefold() not in RUSSIAN_PROVIDERS:
        raise PermissionError("ИИ-помощник работает только с YandexGPT или GigaChat (LLM_PROVIDER)")
    mode = settings.get("sales_ai_mode", "redacted").strip().casefold()
    if mode not in MODES:
        raise PermissionError("sales_ai_mode: redacted | standard | no_cloud")
    if mode == "no_cloud":
        raise PermissionError("Передача текста клиента в облако запрещена (sales_ai_mode = no_cloud)")
    return mode


def prepare_text(text: str, *, mode: str) -> tuple[str, bool]:
    """Donor prepare_sales_ai_text: normalise, bound, redact contacts unless standard."""
    normalized = " ".join(str(text or "").replace("\x00", " ").split())[:MAX_TEXT]
    if not normalized:
        raise ValueError("текст клиента пуст")
    if mode == "standard":
        return normalized, False
    out = _URL.sub("[URL]", _HANDLE.sub("[HANDLE]", redact_text(normalized).text))
    return out, out != normalized


def prompt(lead: sl.Lead, text: str) -> tuple[str, str]:
    return SYSTEM, f"Стадия сделки: {sl.LABELS[lead.stage]}\nСообщение клиента: {text}"


def _flag(d: dict[str, Any], k: str) -> bool:
    v = d.get(k, False)
    if not isinstance(v, bool):
        raise ValueError(f"ответ ИИ: {k} не bool")
    return v


def _unit(d: dict[str, Any], k: str) -> float:
    v = d.get(k, 0)
    if isinstance(v, bool) or not isinstance(v, int | float) or not 0 <= v <= 1:
        raise ValueError(f"ответ ИИ: {k} вне 0..1")
    return float(v)


def parse_analysis(raw: str) -> dict[str, Any]:
    """Strict bounded analysis; anything malformed fails closed."""
    s = str(raw or "").strip()
    s = s[s.find("{") : s.rfind("}") + 1] if "{" in s else s
    try:
        d = json.loads(s)
    except ValueError as exc:
        raise ValueError("ответ ИИ не JSON") from exc
    if not isinstance(d, dict) or d.get("intent") not in INTENTS:
        raise ValueError("ответ ИИ: неизвестный intent")
    reply = " ".join(str(d.get("reply") or "").split())
    if not reply:
        raise ValueError("ответ ИИ без черновика")
    out = {
        k: _flag(d, k)
        for k in (
            "need_is_specific",
            "purchase_intent_explicit",
            "explicit_human_request",
            "sensitive_context",
            "negative_sentiment",
        )
    }
    out |= {k: _unit(d, k) for k in ("purchase_readiness", "confidence")}
    out["intent"] = d["intent"]
    out["reply"] = _URL.sub("", reply)[:MAX_REPLY].strip()
    return out


def milestones(a: dict[str, Any]) -> tuple[str, ...]:
    """Donor validated_sales_ai_milestones: AI may only assert need / qualification, conservatively."""
    if a["confidence"] < 0.90 or a["explicit_human_request"] or a["sensitive_context"] or a["negative_sentiment"]:
        return ("handoff",) if a["explicit_human_request"] or a["sensitive_context"] else ()
    out = []
    if a["need_is_specific"] and a["intent"] in ("service_interest", "pricing", "booking"):
        out.append("need")
        if a["purchase_intent_explicit"] and a["purchase_readiness"] >= 0.75:
            out.append("qualified")
    return tuple(out)


def suggestion(lead: sl.Lead, a: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """lead_note fact with the draft + at most one legal next event for an owner button."""
    legal = None
    for ev in milestones(a):
        if ev == "handoff":
            legal = None if lead.handoff_open else ev
            break
        try:
            if sl.reduce(lead.stage, ev) != lead.stage:
                legal = ev  # one legal step forward only; skips are refused by the shared reducer
                break
        except ValueError:
            continue
    note = {"step": "lead_note", "lead_id": lead.lead_id, "text": ("🤖 Черновик: " + a["reply"])[:300]}
    return note, legal


__all__ = [
    "CANON_SALES_AI",
    "RUSSIAN_PROVIDERS",
    "egress_permit",
    "milestones",
    "parse_analysis",
    "prepare_text",
    "prompt",
    "suggestion",
]
