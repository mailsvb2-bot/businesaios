from __future__ import annotations

from runtime.lazy_namespace import build_owner_namespace

__getattr__, __dir__, __all__ = build_owner_namespace(
    __name__,
    "runtime._internal.effects_actions.llm_completion_support",
    exports=(
        "read_provider_and_model",
        "call_marketing_llm",
        "emit_marketing_llm_success",
        "emit_marketing_llm_error",
    ),
)
