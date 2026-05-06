from __future__ import annotations

"""Pure adapter around EffectsPort for optional LLM marketing.

SECURITY:
- No network/SDK imports here.
- All real HTTP calls must be executed inside sealed runtime effects.
"""

from dataclasses import dataclass
from typing import Optional

from runtime.ports.effects import EffectsPort


@dataclass
class OpenAIChatCompletionsAdapter:
    effects: EffectsPort

    def complete(self, *, system: str, user: str, model: Optional[str] = None) -> str:
        out = self.effects.marketing_llm_complete(  # type: ignore[attr-defined]
            decision_id="-",
            correlation_id="-",
            admin_id="system",
            system=str(system),
            user=str(user),
            model=str(model) if model else None,
        )
        try:
            return str(out.get("text") or "")
        except Exception:
            return ""
