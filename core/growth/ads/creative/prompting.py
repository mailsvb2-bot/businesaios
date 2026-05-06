from __future__ import annotations

from dataclasses import dataclass

from core.llm.contracts import LLMMessage


@dataclass(frozen=True)
class CreativeBrief:
    business_type: str
    offer_title: str
    offer_details: str
    city: str = ""
    tone: str = "friendly"
    language: str = "ru"


def build_messages(brief: CreativeBrief) -> list[LLMMessage]:
    system = (
        "You are a marketing copywriter. Produce SAFE, factual ad copy. "
        "Avoid medical guarantees, shaming, and all-caps. Keep it short."
    )
    user = (
        f"Business: {brief.business_type}\n"
        f"Offer: {brief.offer_title}\n"
        f"Details: {brief.offer_details}\n"
        f"City: {brief.city}\n"
        f"Tone: {brief.tone}\n"
        "Return:\n"
        "- Headline (<=60 chars)\n"
        "- Primary text (<=200 chars)\n"
        "- Description (<=90 chars)\n"
        "- CTA one of: Learn More, Sign Up, Book Now\n"
    )
    return [LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)]
