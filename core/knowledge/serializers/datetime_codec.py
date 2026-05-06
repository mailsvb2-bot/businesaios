from __future__ import annotations

from datetime import datetime


def encode_datetime(value: datetime) -> str:
    return value.isoformat()


def decode_datetime(value: str) -> datetime:
    return datetime.fromisoformat(str(value))
