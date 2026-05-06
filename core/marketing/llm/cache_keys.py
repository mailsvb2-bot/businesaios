from __future__ import annotations

from core.marketing.llm_prompt_builder import MarketingLLMInputs


def build_cache_key(*, cache, provider: str, model: str, inp: MarketingLLMInputs, prompt_version: str, prompt_hash: str, offer_id: str, req) -> str:
    cache_material = "|".join([m.role + ":" + m.content for m in req.messages])
    material = f"{provider}|{model}|{inp.locale}|{inp.experiment}|{inp.variant}|{prompt_version}|{prompt_hash}|{offer_id}|{cache_material}"
    return cache.make_key(material)
