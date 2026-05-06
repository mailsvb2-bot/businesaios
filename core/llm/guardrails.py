from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class GuardrailResult:
    ok: bool
    reason: str = ""
    fixed_text: Optional[str] = None


def require_max_chars(text: str, max_chars: int) -> GuardrailResult:
    if len(text) <= max_chars:
        return GuardrailResult(ok=True)
    return GuardrailResult(ok=True, fixed_text=text[:max_chars].rstrip() + "…")


def forbid_phrases(text: str, phrases: List[str]) -> GuardrailResult:
    low = text.lower()
    for p in phrases:
        if p.lower() in low:
            return GuardrailResult(ok=False, reason=f"forbidden_phrase:{p}")
    return GuardrailResult(ok=True)


def enforce_single_message(text: str) -> GuardrailResult:
    cleaned = " ".join([line.strip() for line in text.splitlines() if line.strip()])
    if not cleaned:
        return GuardrailResult(ok=False, reason="empty")
    return GuardrailResult(ok=True, fixed_text=cleaned)
