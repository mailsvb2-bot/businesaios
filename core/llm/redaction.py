from __future__ import annotations

import re
from dataclasses import dataclass

from security.payload_redaction import redact_free_text

_RE_EMAIL = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Za-z]{2,}\b")
_RE_PHONE = re.compile(r"\b(\+?\d[\d\-\s]{7,}\d)\b")
_RE_CARD = re.compile(r"\b(?:\d[ -]*?){13,19}\b")


@dataclass(frozen=True)
class RedactionResult:
    text: str
    mapping: dict[str, str]


def redact_text(text: str) -> RedactionResult:
    mapping: dict[str, str] = {}

    def _sub(regex: re.Pattern, label: str, s: str) -> str:
        idx = 0

        def repl(m: re.Match) -> str:
            nonlocal idx
            idx += 1
            token = f"<{label}_{idx}>"
            mapping[token] = m.group(0)
            return token

        return regex.sub(repl, s)

    idx = 0

    def secret_replacement(match: re.Match) -> str:
        nonlocal idx
        idx += 1
        token = f"<SECRET_{idx}>"
        mapping[token] = match.group(0)
        return token

    out = redact_free_text(str(text or ""), secret_replacement)
    out = _sub(_RE_EMAIL, "EMAIL", out)
    out = _sub(_RE_PHONE, "PHONE", out)
    out = _sub(_RE_CARD, "CARD", out)
    return RedactionResult(text=out, mapping=mapping)


def safe_metadata(meta: dict) -> dict:
    """Only non-identifying numeric diagnostics may leave the LLM boundary."""
    value = (meta or {}).get("context_tokens")
    return {"context_tokens": value} if type(value) is int and 0 <= value <= 10_000_000 else {}
