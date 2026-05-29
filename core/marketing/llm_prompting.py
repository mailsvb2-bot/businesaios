from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from core.llm.contracts import LLMMessage, LLMRequest
from core.llm.redaction import redact_text


@dataclass(frozen=True)
class MarketingLLMInputs:
    tenant_id: str
    user_id: str
    locale: str
    channel: str
    features: dict[str, Any]
    offer: dict[str, Any]
    last_user_text: str = ""
    correlation_id: str = ""
    message_id: str = ""
    experiment: str = ""
    variant: str = ""


PROMPT_VERSION = "marketing_v1.0"  # frozen prompt version


SYSTEM_PROMPT = (
    "You are a marketing copy assistant for a wellbeing product. "
    "Your job is to write ONE short message for the user in their language. "
    "Rules: "
    "1) Do NOT invent facts. Use only provided inputs. "
    "2) Do NOT mention internal systems, 'DecisionCore', 'features', tokens, models. "
    "3) Do NOT ask many questions: максимум 1 короткий вопрос. "
    "4) Telegram style: 1 message, <= 450 chars, friendly, concrete, no hype. "
    "5) If the offer is paid, reduce risk: explain what exactly user gets. "
    "6) NEVER change price/currency; copy them exactly. "
)


def _prompt_hash(system_prompt: str, user_prompt: str) -> str:
    h = hashlib.sha256()
    h.update(system_prompt.encode("utf-8"))
    h.update(b"\n---\n")
    h.update(user_prompt.encode("utf-8"))
    return h.hexdigest()


def build_marketing_messages(inp: MarketingLLMInputs) -> list[LLMMessage]:
    red = redact_text(inp.last_user_text or "")
    offer = inp.offer or {}
    f = inp.features or {}

    compact_features = {
        k: f.get(k)
        for k in [
            "segment",
            "need_score",
            "risk_score",
            "ability_to_pay",
            "listen_ratio_7d",
            "streak_days",
            "last_seen_days",
        ]
        if k in f
    }

    user_prompt = (
        f"prompt_version: {PROMPT_VERSION}\n"
        f"Locale: {inp.locale}\n"
        f"Channel: {inp.channel}\n"
        f"Experiment: {inp.experiment}\n"
        f"Variant: {inp.variant}\n"
        f"Offer:\n"
        f"- id: {offer.get('id','')}\n"
        f"- title: {offer.get('title','')}\n"
        f"- price: {offer.get('price','')}\n"
        f"- currency: {offer.get('currency','')}\n"
        f"- what_user_gets: {offer.get('what_user_gets','')}\n"
        f"User context:\n"
        f"- last_user_text: {red.text}\n"
        f"- features: {compact_features}\n"
        f"Task: write ONE message (<=450 chars) that naturally offers the offer. "
        f"Tone: calm, respectful, pragmatic. "
        f"Output only the message text."
    )

    return [
        LLMMessage(role="system", content=SYSTEM_PROMPT),
        LLMMessage(role="user", content=user_prompt),
    ]


def build_marketing_request(
    *,
    model: str,
    inp: MarketingLLMInputs,
    temperature: float = 0.5,
    max_tokens: int = 220,
) -> tuple[LLMRequest, str, str]:
    messages = build_marketing_messages(inp)
    user_prompt = messages[-1].content
    ph = _prompt_hash(SYSTEM_PROMPT, user_prompt)
    req = LLMRequest(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        metadata={
            "kind": "marketing_message",
            "prompt_version": PROMPT_VERSION,
            "prompt_hash": ph,
            "tenant_id": inp.tenant_id,
            "channel": inp.channel,
            "locale": inp.locale,
            "experiment": inp.experiment,
            "variant": inp.variant,
            "correlation_id": inp.correlation_id,
            "message_id": inp.message_id,
            "offer_id": (inp.offer or {}).get("id", ""),
        },
    )
    return req, PROMPT_VERSION, ph
