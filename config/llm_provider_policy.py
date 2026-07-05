from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class LLMProviderPolicy:
    default_openai_compat_model: str = "gpt-4.1-mini"
    default_timeout_s: int = 20
    mock_fixed_text: str = "OK"


DEFAULT_LLM_PROVIDER_POLICY = LLMProviderPolicy()


__all__ = ["LLMProviderPolicy", "DEFAULT_LLM_PROVIDER_POLICY"]
