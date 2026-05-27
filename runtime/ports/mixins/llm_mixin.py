"""LLM-specific effects protocol mixin.

Extracted from EffectsPort (Patch 05).
"""

from __future__ import annotations

from typing import Any, Protocol


class EffectsLLMMixin(Protocol):
    """LLM side-effect methods (marketing composition, etc.)."""

    def llm_generate(self, **kw: Any) -> Any: ...
    def llm_compose_marketing(self, **kw: Any) -> Any: ...
