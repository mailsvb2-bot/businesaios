from __future__ import annotations

import re
from dataclasses import dataclass

_RE_EMAIL = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Za-z]{2,}\b")
_RE_PHONE = re.compile(r"\b(\+?\d[\d\-\s]{7,}\d)\b")
_RE_CARD = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_RE_TOKENLIKE = re.compile(r"\b(sk-[A-Za-z0-9]{10,}|AIza[A-Za-z0-9\-_]{10,})\b")
_RE_URL = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>]+")
_RE_HANDLE = re.compile(r"(?<![\w@])@[A-Za-z0-9_]{2,64}\b")
_RE_LONG_ID = re.compile(r"\b\d{8,}\b")


@dataclass(frozen=True)
class RedactionResult:
    text: str
    mapping: dict[str, str]


@dataclass(frozen=True)
class PreparedSalesAIText:
    text: str
    redacted: bool


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

    out = str(text or "")
    out = _sub(_RE_TOKENLIKE, "SECRET", out)
    out = _sub(_RE_EMAIL, "EMAIL", out)
    out = _sub(_RE_URL, "URL", out)
    out = _sub(_RE_HANDLE, "HANDLE", out)
    out = _sub(_RE_PHONE, "PHONE", out)
    out = _sub(_RE_CARD, "CARD", out)
    out = _sub(_RE_LONG_ID, "ID", out)
    return RedactionResult(text=out, mapping=mapping)


def prepare_sales_ai_text(
    text: str,
    *,
    data_mode: str,
    max_chars: int = 6000,
) -> PreparedSalesAIText:
    bounded = " ".join(str(text or "").replace("\x00", " ").split())
    if not bounded:
        raise ValueError("sales AI text must not be empty")
    if isinstance(max_chars, bool) or int(max_chars) < 1:
        raise ValueError("max_chars must be positive")
    bounded = bounded[: int(max_chars)]
    mode = str(data_mode or "").strip().casefold()
    if mode == "no_cloud":
        raise PermissionError("sales_ai_no_cloud")
    if mode == "standard":
        return PreparedSalesAIText(text=bounded, redacted=False)
    if mode != "redacted":
        raise ValueError("unsupported sales AI data mode")
    result = redact_text(bounded)
    return PreparedSalesAIText(text=result.text, redacted=bool(result.mapping))


def safe_metadata(meta: dict) -> dict:
    allow: dict = {}
    for k, v in (meta or {}).items():
        if str(k).lower() in {"user_text", "prompt", "messages", "email", "phone", "card"}:
            continue
        if isinstance(v, str | int | float | bool) and len(str(v)) <= 256:
            allow[k] = v
    return allow


__all__ = [
    "PreparedSalesAIText",
    "RedactionResult",
    "prepare_sales_ai_text",
    "redact_text",
    "safe_metadata",
]
