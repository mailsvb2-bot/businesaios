from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict


_RE_EMAIL = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Za-z]{2,}\b")
_RE_PHONE = re.compile(r"\b(\+?\d[\d\-\s]{7,}\d)\b")
_RE_CARD = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_RE_TOKENLIKE = re.compile(r"\b(sk-[A-Za-z0-9]{10,}|AIza[A-Za-z0-9\-_]{10,})\b")


@dataclass(frozen=True)
class RedactionResult:
    text: str
    mapping: Dict[str, str]


def redact_text(text: str) -> RedactionResult:
    mapping: Dict[str, str] = {}

    def _sub(regex: re.Pattern, label: str, s: str) -> str:
        idx = 0

        def repl(m: re.Match) -> str:
            nonlocal idx
            idx += 1
            token = f"<{label}_{idx}>"
            mapping[token] = m.group(0)
            return token

        return regex.sub(repl, s)

    out = str(text or "")
    out = _sub(_RE_TOKENLIKE, "SECRET", out)
    out = _sub(_RE_EMAIL, "EMAIL", out)
    out = _sub(_RE_PHONE, "PHONE", out)
    out = _sub(_RE_CARD, "CARD", out)
    return RedactionResult(text=out, mapping=mapping)


def safe_metadata(meta: Dict) -> Dict:
    allow: Dict = {}
    for k, v in (meta or {}).items():
        if str(k).lower() in {"user_text", "prompt", "messages", "email", "phone", "card"}:
            continue
        if isinstance(v, (str, int, float, bool)) and len(str(v)) <= 256:
            allow[k] = v
    return allow
