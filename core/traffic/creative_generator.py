"""Ad creative generator — deterministic fallback + LLM-powered upgrade.

Architecture:
  CreativeGenerator      — sync, pure, no I/O (domain default, always works)
  LLMCreativeGenerator   — sync/async bridge over canonical LLMClient

TrafficStrategyService uses CreativeGenerator by default.
Boot builder upgrades to LLMCreativeGenerator when LLM_ENABLED=1.
"""

from __future__ import annotations


import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

from core.llm.agent.parse import extract_json_block
from core.traffic.contracts import TrafficCreative

logger = logging.getLogger(__name__)


def _normalize_cta(value: Any) -> str:
    text = str(value or "Написать").strip()
    if text in _ALLOWED_CTA:
        return text
    return _CTA_ALIASES.get(text.lower(), "Написать")


def _normalize_interests(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= 8:
            break
    return out

_PROMPT_VERSION = "ad_creative_v1.0"
_ALLOWED_CTA = {"Написать", "Узнать больше", "Записаться", "Получить предложение"}
_CTA_ALIASES = {
    "написать": "Написать",
    "узнать больше": "Узнать больше",
    "записаться": "Записаться",
    "получить предложение": "Получить предложение",
}

_SYSTEM_PROMPT = (
    "You are an expert ad copywriter for a small business in Russia. "
    "Write ONE ad creative for the given product/service.\n"
    "Rules:\n"
    "1) Respond ONLY with valid JSON — no markdown, no preamble.\n"
    '2) Schema: {"headline": str, "primary_text": str, "cta": str, "interests": [str, ...]}\n'
    "3) headline: max 60 chars, punchy, in Russian.\n"
    "4) primary_text: max 120 chars, clear benefit, in Russian.\n"
    '5) cta: one of ["Написать", "Узнать больше", "Записаться", "Получить предложение"].\n'
    "6) interests: 2-5 short English targeting tags (e.g. \"healthcare\", \"fitness\").\n"
    "7) Do NOT invent prices or facts — use only what is provided.\n"
)


def _user_prompt(*, what: str, offer_title: str, region: str, seed: str) -> str:
    return (
        f"Product/service: {what}\n"
        f"Offer title: {offer_title}\n"
        f"Target region: {region}\n"
        f"Variant seed: {seed}\n"
        "Write the ad creative."
    )


@dataclass(frozen=True)
class CreativeGenerator:
    """Deterministic ad creative generator (pure domain default, no I/O)."""

    def build(self, *, what: str, offer_title: str, seed: str = "v1") -> TrafficCreative:
        _ = seed
        headline = str(offer_title or "Специальное предложение")[:60]
        primary = (
            f"{(what or 'Услуга').strip()[:80]}. "
            "Быстро, прозрачно, без лишнего. Напишите, чтобы узнать детали."
        )
        return TrafficCreative(headline=headline, primary_text=primary, cta="Написать")


class LLMCreativeGenerator:
    """LLM-powered ad creative: headline + copy + targeting interests.

    Falls back to CreativeGenerator on any recoverable LLM error (network, parse,
    timeout, invalid payload). There is still a single decision path: the LLM may
    propose copy, but it does not pick actions or bypass runtime gates.
    """

    def __init__(
        self,
        llm: Any,
        *,
        model: str = "gpt-4.1-mini",
        temperature: float = 0.5,
        max_tokens: int = 300,
        timeout_s: float = 15.0,
    ) -> None:
        self._llm = llm
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout_s = timeout_s
        self._fallback = CreativeGenerator()

    def _build_request(self, *, what: str, offer_title: str, region: str = "", seed: str = "v1"):
        from core.llm.contracts import LLMMessage, LLMRequest

        return LLMRequest(
            messages=[
                LLMMessage(role="system", content=_SYSTEM_PROMPT),
                LLMMessage(
                    role="user",
                    content=_user_prompt(
                        what=what, offer_title=offer_title, region=region, seed=seed
                    ),
                ),
            ],
            model=self._model,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            timeout_s=self._timeout_s,
        )

    def _parse_response(self, *, resp: Any, offer_title: str) -> tuple[TrafficCreative, list[str]]:
        raw_text = str(getattr(resp, "content", "") or "").strip()
        json_data = None
        if raw_text:
            try:
                json_data = json.loads(raw_text)
            except json.JSONDecodeError:
                json_data, _rest = extract_json_block(raw_text)
        if not isinstance(json_data, dict):
            raise ValueError("LLM returned non-JSON creative payload")

        headline = str(json_data.get("headline") or offer_title)[:60]
        primary_text = str(json_data.get("primary_text") or "")[:200]
        cta = _normalize_cta(json_data.get("cta"))
        interests = _normalize_interests(json_data.get("interests"))
        if not primary_text:
            raise ValueError("LLM returned empty primary_text")
        creative = TrafficCreative(headline=headline, primary_text=primary_text, cta=cta)
        return creative, interests

    def _fallback_result(self, *, what: str, offer_title: str, seed: str) -> tuple[TrafficCreative, list[str]]:
        return self._fallback.build(what=what, offer_title=offer_title, seed=seed), []

    async def generate_async(
        self,
        *,
        what: str,
        offer_title: str,
        region: str = "",
        seed: str = "v1",
    ) -> tuple[TrafficCreative, list[str]]:
        try:
            req = self._build_request(what=what, offer_title=offer_title, region=region, seed=seed)
            resp = await self._llm.generate(req)
            creative, interests = self._parse_response(resp=resp, offer_title=offer_title)
            logger.debug(
                "[LLMCreativeGenerator] ok headline=%r cta=%r interests=%s version=%s",
                creative.headline, creative.cta, interests, _PROMPT_VERSION,
            )
            return creative, interests

        except (AttributeError, TypeError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
            logger.warning(
                "[LLMCreativeGenerator] fallback: %r (what=%r offer=%r)",
                exc, what, offer_title,
            )
            return self._fallback_result(what=what, offer_title=offer_title, seed=seed)

    def build_with_interests(
        self,
        *,
        what: str,
        offer_title: str,
        region: str = "",
        seed: str = "v1",
    ) -> tuple[TrafficCreative, list[str]]:
        try:
            generate_sync = getattr(self._llm, "generate_sync", None)
            if callable(generate_sync):
                req = self._build_request(what=what, offer_title=offer_title, region=region, seed=seed)
                resp = generate_sync(req)
                return self._parse_response(resp=resp, offer_title=offer_title)
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop is not None and loop.is_running():
                logger.warning(
                    "[LLMCreativeGenerator] build_with_interests() in async context — using fallback"
                )
                return self._fallback_result(what=what, offer_title=offer_title, seed=seed)
            from core.marketing.async_runner import run_awaitable_sync

            return run_awaitable_sync(
                self.generate_async(what=what, offer_title=offer_title, region=region, seed=seed)
            )
        except (AttributeError, TypeError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
            logger.warning(
                "[LLMCreativeGenerator] sync fallback: %r (what=%r offer=%r)",
                exc, what, offer_title,
            )
            return self._fallback_result(what=what, offer_title=offer_title, seed=seed)

    def build(self, *, what: str, offer_title: str, seed: str = "v1") -> TrafficCreative:
        creative, _ = self.build_with_interests(what=what, offer_title=offer_title, seed=seed)
        return creative
