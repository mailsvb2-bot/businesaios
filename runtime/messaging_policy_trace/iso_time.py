from __future__ import annotations

from datetime import UTC, datetime, timezone


def parse_iso_to_epoch_ms(value: str) -> int:
    text = str(value or '').strip()
    if not text:
        return 0
    dt = datetime.fromisoformat(text.replace('Z', '+00:00'))
    return int(dt.timestamp() * 1000)


def safe_parse_iso_to_epoch_ms(value: str) -> int:
    try:
        return parse_iso_to_epoch_ms(value)
    except Exception:
        return 0


def epoch_ms_to_iso(value: int) -> str:
    if int(value or 0) <= 0:
        return ''
    return datetime.fromtimestamp(int(value) / 1000.0, tz=UTC).isoformat()
