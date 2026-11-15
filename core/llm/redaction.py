from __future__ import annotations

import re
from dataclasses import dataclass

_RE_EMAIL = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Za-z]{2,}\b")
_RE_PHONE = re.compile(r"\b(\+?\d[\d\-\s]{7,}\d)\b")
_RE_CARD = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_RE_SECRET = re.compile(r'(?i)\b(?:Bearer[ \t]+[A-Za-z0-9._~+/=-]+|\d{6,12}:[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9_-]{10,}|AIza[A-Za-z0-9_-]{10,}|live_[A-Za-z0-9]{16,}|(?:password|passwd|api[_-]?key|token|authorization|cookie|set-cookie|client_secret|refresh_token|secret)["\']?[ \t]*[:=][ \t]*(?:"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[^,\r\n]+))')


@dataclass(frozen=True)
class RedactionResult:
    text: str
    mapping: dict[str, str]


def redact_free_text(text: str, replacement: str = "***REDACTED***") -> str:
    return _RE_SECRET.sub(replacement, str(text))


def redact_text(text: str) -> RedactionResult:
    mapping: dict[str, str] = {}
    counters: dict[str, int] = {}

    def _sub(regex: re.Pattern, label: str, s: str) -> str:
        def repl(m: re.Match) -> str:
            counters[label] = counters.get(label, 0) + 1
            token = f"<{label}_{counters[label]}>"
            mapping[token] = m.group(0)
            return token
        return regex.sub(repl, s)

    out = str(text or "")
    for regex, label in ((_RE_SECRET, "SECRET"), (_RE_EMAIL, "EMAIL"), (_RE_PHONE, "PHONE"), (_RE_CARD, "CARD")):
        out = _sub(regex, label, out)
    return RedactionResult(text=out, mapping=mapping)


def safe_metadata(meta: dict) -> dict:
    """Only non-identifying numeric diagnostics may leave the LLM boundary."""
    value = (meta or {}).get("context_tokens")
    return {"context_tokens": value} if type(value) is int and 0 <= value <= 10_000_000 else {}
