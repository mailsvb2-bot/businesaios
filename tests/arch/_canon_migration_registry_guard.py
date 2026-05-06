from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "docs" / "CANON_MIGRATION_DEPRECATION_REGISTRY_DATA_V1.yaml"

REQUIRED_KEYS: tuple[str, ...] = (
    "migration_id",
    "kind",
    "scope",
    "reason",
    "owner",
    "created_on",
    "target_date",
    "status",
    "from_paths",
    "to_paths",
    "canonical_target",
)

ALLOWED_KINDS: tuple[str, ...] = (
    "deprecation",
    "migration",
    "rename",
    "boundary_refactor",
    "legacy_removal",
)

ALLOWED_STATUSES: tuple[str, ...] = (
    "planned",
    "active",
    "blocked",
    "completed",
    "expired",
)


@dataclass(frozen=True)
class CanonMigration:
    migration_id: str
    kind: str
    scope: str
    reason: str
    owner: str
    created_on: str
    target_date: str
    status: str
    from_paths: tuple[str, ...]
    to_paths: tuple[str, ...]
    canonical_target: str

    def created_date(self) -> date:
        return date.fromisoformat(self.created_on)

    def target(self) -> date:
        return date.fromisoformat(self.target_date)

    def is_expired(self, today: date) -> bool:
        return self.target() < today


def read_registry_text() -> str:
    return REGISTRY_PATH.read_text(encoding="utf-8")


def _strip_comment(line: str) -> str:
    if "#" in line:
        return line.split("#", 1)[0].rstrip()
    return line.rstrip()


def _unquote(value: str) -> str:
    if len(value) >= 2 and (
        (value[0] == '"' and value[-1] == '"')
        or (value[0] == "'" and value[-1] == "'")
    ):
        return value[1:-1]
    return value


def _parse_key_value(text: str) -> tuple[str, str]:
    if ":" not in text:
        raise ValueError(f"Invalid registry line: {text}")
    key, value = text.split(":", 1)
    return key.strip(), _unquote(value.strip())


def _to_migration(item: dict[str, Any]) -> CanonMigration:
    missing = [key for key in REQUIRED_KEYS if key not in item]
    if missing:
        raise ValueError(f"Missing keys in migration registry item: {', '.join(missing)}")

    from_paths = item["from_paths"]
    to_paths = item["to_paths"]

    if not isinstance(from_paths, list):
        raise ValueError("Migration registry item from_paths must be a list")
    if not isinstance(to_paths, list):
        raise ValueError("Migration registry item to_paths must be a list")

    return CanonMigration(
        migration_id=str(item["migration_id"]),
        kind=str(item["kind"]),
        scope=str(item["scope"]),
        reason=str(item["reason"]),
        owner=str(item["owner"]),
        created_on=str(item["created_on"]),
        target_date=str(item["target_date"]),
        status=str(item["status"]),
        from_paths=tuple(str(path) for path in from_paths),
        to_paths=tuple(str(path) for path in to_paths),
        canonical_target=str(item["canonical_target"]),
    )


def load_registry() -> list[CanonMigration]:
    if not REGISTRY_PATH.exists():
        return []

    raw = read_registry_text().splitlines()
    lines = [_strip_comment(line) for line in raw]

    if not any(line.strip() for line in lines):
        return []

    migrations: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_list_key: str | None = None

    for raw_line in lines:
        line = raw_line.rstrip("\n")
        if not line.strip():
            continue

        stripped = line.strip()

        if stripped == "migrations:":
            continue

        if stripped.startswith("- "):
            if current_list_key in {"from_paths", "to_paths"} and current is not None:
                current.setdefault(current_list_key, []).append(_unquote(stripped[2:].strip()))
                continue

            if current is not None:
                migrations.append(current)

            current = {}
            current_list_key = None

            remainder = stripped[2:].strip()
            if remainder:
                key, value = _parse_key_value(remainder)
                current[key] = value
            continue

        if current is None:
            continue

        if stripped in {"from_paths:", "to_paths:"}:
            current_list_key = stripped[:-1]
            current[current_list_key] = []
            continue

        key, value = _parse_key_value(stripped)
        current[key] = value
        current_list_key = None

    if current is not None:
        migrations.append(current)

    return [_to_migration(item) for item in migrations]
