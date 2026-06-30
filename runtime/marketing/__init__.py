"""Canonical runtime package alias namespace for runtime.marketing public API."""

from __future__ import annotations


from runtime.package_alias_namespace import build_package_alias_namespace

CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE = True

_PUBLIC_ATTRS = {
    "MarketingLLMInputs": ("core.marketing.llm_prompt_builder", "MarketingLLMInputs"),
    "compose_marketing_fallback": ("core.marketing.llm_templates", "compose_marketing_fallback"),
    "compose_marketing_text_sync": ("core.marketing.llm.service", "compose_marketing_text_sync"),
    "LLMComposerConfig": ("core.marketing.llm_composer", "LLMComposerConfig"),
    "MarketingLLMComposer": ("core.marketing.llm_composer", "MarketingLLMComposer"),
}

__getattr__, __dir__, __all__ = build_package_alias_namespace(
    __name__,
    _PUBLIC_ATTRS,
    extra_exports=['CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE'],
    )

