from __future__ import annotations

import hashlib
from dataclasses import replace

from core.marketing.llm_guardrails import validate_marketing_text
from core.marketing.llm_postprocess import normalize_generated_text
from core.marketing.llm_prompt_builder import MarketingLLMInputs, build_marketing_request
from core.telemetry.trace_utils import new_id, now_ms


def start_request() -> tuple[str, int]:
    return new_id("llm"), now_ms()


def build_request(*, model: str, inp: MarketingLLMInputs):
    return build_marketing_request(model=model, inp=inp)


def build_cache_key(*, cache, provider: str, model: str, inp: MarketingLLMInputs, prompt_version: str, prompt_hash: str, offer_id: str, req) -> str:
    material = "|".join(m.role + ":" + m.content for m in req.messages)
    return cache.make_key("|".join((
        str(inp.tenant_id), str(inp.user_id), provider, model, str(inp.locale), str(inp.channel),
        str(inp.experiment), str(inp.variant), prompt_version, prompt_hash, offer_id, material,
    )))


def finalize_text(*, text: str, max_chars: int, forbid: tuple, offer: dict) -> tuple[bool, str | None, str]:
    ok, clean, reason = validate_marketing_text(
        text=normalize_generated_text(text or ""), max_chars=int(max_chars), forbid=forbid, offer=offer or {},
    )
    return bool(ok), clean, str(reason)


def idempotent_request_id(*, inp: MarketingLLMInputs, provider: str, model: str, generated: str) -> str:
    source_id = str(inp.message_id or inp.correlation_id or "").strip()
    if not source_id:
        return generated
    return "llm-" + hashlib.sha256("\0".join((
        str(inp.tenant_id), str(inp.user_id), str(inp.channel), source_id,
    )).encode("utf-8")).hexdigest()[:32]


def with_accounting_metadata(*, request, inp: MarketingLLMInputs, request_id: str, prompt_version: str, prompt_hash: str):
    metadata = dict(request.metadata or {})
    metadata.update({key: str(value or "") for key, value in {
        "tenant_id": inp.tenant_id, "user_id": inp.user_id,
        "correlation_key": inp.correlation_id or inp.message_id or request_id,
        "task_type": "marketing_message", "request_id": request_id,
        "channel": inp.channel, "locale": inp.locale, "kind": "marketing_message",
        "message_id": inp.message_id, "offer_id": (inp.offer or {}).get("id"),
        "experiment": inp.experiment, "variant": inp.variant,
        "prompt_version": prompt_version, "prompt_hash": prompt_hash,
    }.items()})
    return replace(request, metadata=metadata)
