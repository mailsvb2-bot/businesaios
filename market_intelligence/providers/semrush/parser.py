from __future__ import annotations

import csv
import io


def parse_semrush_table(text: str) -> list[dict[str, str]]:
    stripped = text.strip()
    if not stripped:
        return []
    if stripped.startswith('ERROR '):
        raise ValueError(stripped.splitlines()[0])
    reader = csv.DictReader(io.StringIO(stripped), delimiter=';')
    return [{str(key): str(value or '') for key, value in row.items()} for row in reader]


def to_int(value: str | None) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def to_float(value: str | None) -> float | None:
    try:
        return float(str(value).replace(',', '.').strip())
    except (TypeError, ValueError):
        return None
