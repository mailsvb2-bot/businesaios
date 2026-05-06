from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "docs" / "CANON_EXCEPTION_REGISTRY_DATA_V1.yaml"

REQUIRED_KEYS: tuple[str, ...] = (
    "exception_id",
    "scope",
    "reason",
    "owner",
    "created_on",
    "expires_on",
    "canonical_rule",
    "paths",
    "status",
)

ALLOWED_STATUSES: tuple[str, ...] = (
    "active",
    "expired",
    "closed",
)


@dataclass(frozen=True)
class CanonException:
    exception_id: str
    scope: str
    reason: str
    owner: str
    created_on: str
    expires_on: str
    canonical_rule: str
    paths: tuple[str, ...]
    status: str

    def created_date(self) -> date:
        return date.fromisoformat(self.created_on)

    def expires_date(self) -> date:
        return date.fromisoformat(self.expires_on)

    def is_expired(self, today: date) -> bool:
        return self.expires_date() < today


def read_registry_text() -> str:
    return REGISTRY_PATH.read_text(encoding="utf-8")


def _strip_comment(line: str) -> str:
    if "#" in line:
        return line.split("#", 1)[0].rstrip()
    return line.rstrip()


def _parse_key_value(text: str) -> tuple[str, str]:
    if ":" not in text:
        raise ValueError(f"Invalid registry line: {text}")
    key, value = text.split(":", 1)
    return key.strip(), _unquote(value.strip())


def _unquote(value: str) -> str:
    if len(value) >= 2 and (
        (value[0] == '"' and value[-1] == '"')
        or (value[0] == "'" and value[-1] == "'")
    ):
        return value[1:-1]
    return value


def _to_exception(item: dict[str, Any]) -> CanonException:
    missing = [key for key in REQUIRED_KEYS if key not in item]
    if missing:
        raise ValueError(f"Missing keys in exception registry item: {', '.join(missing)}")

    paths = item["paths"]
    if not isinstance(paths, list):
        raise ValueError("Exception registry item paths must be a list")

    return CanonException(
        exception_id=str(item["exception_id"]),
        scope=str(item["scope"]),
        reason=str(item["reason"]),
        owner=str(item["owner"]),
        created_on=str(item["created_on"]),
        expires_on=str(item["expires_on"]),
        canonical_rule=str(item["canonical_rule"]),
        paths=tuple(str(path) for path in paths),
        status=str(item["status"]),
    )


def load_registry() -> list[CanonException]:
    if not REGISTRY_PATH.exists():
        return []

    raw = read_registry_text().splitlines()
    lines = [_strip_comment(line) for line in raw]

    if not any(line.strip() for line in lines):
        return []

    exceptions: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    in_paths = False

    for raw_line in lines:
        line = raw_line.rstrip("\n")
        if not line.strip():
            continue

        stripped = line.strip()

        if stripped == "exceptions:":
            continue

        if stripped.startswith("- "):
            if in_paths and current is not None:
                current.setdefault("paths", []).append(_unquote(stripped[2:].strip()))
                continue

            if current is not None:
                exceptions.append(current)

            current = {}
            in_paths = False

            remainder = stripped[2:].strip()
            if remainder:
                key, value = _parse_key_value(remainder)
                current[key] = value
            continue

        if current is None:
            continue

        if stripped == "paths:":
            current["paths"] = []
            in_paths = True
            continue

        key, value = _parse_key_value(stripped)
        current[key] = value
        in_paths = False

    if current is not None:
        exceptions.append(current)

    return [_to_exception(item) for item in exceptions]


def all_registry_paths(exceptions: list[CanonException]) -> list[str]:
    result: list[str] = []
    for item in exceptions:
        result.extend(item.paths)
    return sorted(set(result))
