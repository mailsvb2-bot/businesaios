from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class MigrationChange:
    path: str
    changed: bool
    notes: list[str]


TARGET_SUFFIXES = (".py",)

IMPORT_PATTERN = re.compile(
    r"from\s+core\.economics\.ltv_world_model\s+import\s+([^\n]+)"
)

LEGACY_INIT_PATTERN = re.compile(
    r"WorldModel\s*\(\s*LTVModel\s*\(\s*\)\s*\)"
)

BUILDER_IMPORT_LINE = "from bootstrap.world_model_builder import build_default_world_model"


def migrate_file(path: Path) -> MigrationChange:
    try:
        original = path.read_text(encoding="utf-8")
    except Exception:
        return MigrationChange(path=str(path), changed=False, notes=["read_failed"])

    text = original
    notes: list[str] = []

    match = IMPORT_PATTERN.search(text)
    if match:
        imported = [item.strip() for item in match.group(1).split(",")]
        filtered = [item for item in imported if item not in {"WorldModel", "LTVModel"}]

        if filtered:
            replacement = f"from core.economics.ltv_world_model import {', '.join(filtered)}"
        else:
            replacement = ""

        text = IMPORT_PATTERN.sub(replacement, text, count=1)
        notes.append("removed_legacy_world_model_import")

    if LEGACY_INIT_PATTERN.search(text):
        text = LEGACY_INIT_PATTERN.sub("build_default_world_model()", text)
        notes.append("replaced_worldmodel_ltvmodel_constructor")

        if BUILDER_IMPORT_LINE not in text:
            text = _inject_builder_import(text)
            notes.append("added_builder_import")

    text = _cleanup_blank_lines(text)

    if text == original:
        return MigrationChange(path=str(path), changed=False, notes=[])

    path.write_text(text, encoding="utf-8")
    return MigrationChange(path=str(path), changed=True, notes=notes)


def _inject_builder_import(text: str) -> str:
    lines = text.splitlines()
    insert_at = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("from ") or stripped.startswith("import "):
            insert_at = i + 1

    lines.insert(insert_at, BUILDER_IMPORT_LINE)
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def _cleanup_blank_lines(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"^\s*\n", "", text)
    return text


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    changes: list[MigrationChange] = []

    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in TARGET_SUFFIXES:
            continue
        if path.name.startswith("."):
            continue
        if any(part in {"venv", ".venv", "__pycache__", ".git", ".pytest_cache", "node_modules"} for part in path.parts):
            continue

        change = migrate_file(path)
        if change.changed:
            changes.append(change)

    payload = {
        "ok": True,
        "changed_files": len(changes),
        "changes": [
            {
                "path": c.path,
                "notes": c.notes,
            }
            for c in changes
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
