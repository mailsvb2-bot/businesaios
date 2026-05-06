from __future__ import annotations


def clean_text(value: object | None, *, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def clamp_int(value: object | None, *, default: int, lower: int, upper: int) -> int:
    try:
        out = int(value)
    except Exception:
        out = int(default)
    return max(int(lower), min(out, int(upper)))
