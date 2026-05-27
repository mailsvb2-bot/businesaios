from __future__ import annotations

from typing import Optional

from core.marketing.llm_guardrails import validate_marketing_text
from core.marketing.llm_postprocess import normalize_generated_text
from core.marketing.llm_prompt_builder import MarketingLLMInputs, build_marketing_request
from core.telemetry.trace_utils import new_id, now_ms


def start_request() -> tuple[str, int]:
    return new_id("llm"), now_ms()


def build_request(*, model: str, inp: MarketingLLMInputs):
    return build_marketing_request(model=model, inp=inp)


def finalize_text(*, text: str, max_chars: int, forbid: tuple, offer: dict) -> tuple[bool, Optional[str], str]:
    normalized = normalize_generated_text(text or "")
    ok_text, clean_text, guard_reason = validate_marketing_text(
        text=normalized,
        max_chars=int(max_chars),
        forbid=forbid,
        offer=(offer or {}),
    )
    return bool(ok_text), clean_text, str(guard_reason)
