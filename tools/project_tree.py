from __future__ import annotations

"""Repository tree inspection helper.

This is an engineering/debugging tool only. It does not assemble runtime,
choose policies, execute actions, or participate in DecisionCore flow.
"""

import argparse
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from fnmatch import fnmatch
import json
from pathlib import Path
import sys

CANON_PROJECT_TREE_TOOL = True
CANON_PROJECT_TREE_TOOL_NO_RUNTIME_ASSEMBLY = True
CANON_PROJECT_TREE_TOOL_NO_DECISION_LOGIC = True

DEFAULT_EXCLUDE_NAMES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "artifacts",
        "build",
        "dist",
        "htmlcov",
        "node_modules",
        "target",
    }
)
DEFAULT_EXCLUDE_SUFFIXES = (
    ".db",
    ".log",
    ".pyc",
    ".pyo",
    ".sqlite",
    ".sqlite3",
)
DEFAULT_EXCLUDE_PATH_PATTERNS = (
    "data/business_autonomy/*",
    "runtime/data/security/*",
    "security/process_owner_security_audit.jsonl",
)


@dataclass(frozen=True)
class ProjectTreeEntry:
    path: str
    name: str
    kind: str
    depth: int
    children: tuple["ProjectTreeEntry", ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "name": self.name,
            "kind": self.kind,
            "depth": self.depth,
            "children": [child.to_dict() for child in self.children],
        }


@dataclass(frozen=True)
class ProjectTreeSummary:
    root: str
    directories: int
    files: int
    skipped: int
    truncated: bool
    max_depth: int
    include_files: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "root": self.root,
            "directories": self.directories,
            "files": self.files,
            "skipped": self.skipped,
            "truncated": self.truncated,
            "max_depth": self.max_depth,
            "include_files": self.include_files,
        }


@dataclass(frozen=True)
class ProjectTreeResult:
    root: ProjectTreeEntry
    summary: ProjectTreeSummary

    def to_dict(self) -> dict[str, object]:
        return {"summary": self.summary.to_dict(), "tree": self.root.to_dict()}


@dataclass
class _WalkState:
    directories: int = 0
    files: int = 0
    skipped: int = 0
    emitted: int = 0
    truncated: bool = False


def _normalize_rel(path: Path) -> str:
    return path.as_posix() or "."


def _matches_any(value: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch(value, pattern) for pattern in patterns)


def _is_excluded(path: Path, *, root: Path, default_excludes: bool, extra_excludes: Sequence[str]) -> bool:
    rel = _normalize_rel(path.relative_to(root))
    name = path.name
    patterns = [*extra_excludes]
    if default_excludes:
        if name in DEFAULT_EXCLUDE_NAMES:
            return True
        if path.is_file() and name.endswith(DEFAULT_EXCLUDE_SUFFIXES):
            return True
        patterns.extend(DEFAULT_EXCLUDE_PATH_PATTERNS)
    return _matches_any(name, patterns) or _matches_any(rel, patterns)


def _sorted_children(path: Path, *, include_files: bool) -> list[Path]:
    try:
        children = list(path.iterdir())
    except OSError:
        return []
    if not include_files:
        children = [child for child in children if child.is_dir()]
    return sorted(children, key=lambda item: (not item.is_dir(), item.name.casefold()))


def build_project_tree(
    root: str | Path = ".",
    *,
    max_depth: int = 4,
    include_files: bool = True,
    default_excludes: bool = True,
    extra_excludes: Sequence[str] = (),
    max_entries: int = 10_000,
) -> ProjectTreeResult:
    root_path = Path(root).resolve()
    if not root_path.exists():
        raise FileNotFoundError(str(root_path))
    if not root_path.is_dir():
        raise NotADirectoryError(str(root_path))
    if max_depth < 0:
        raise ValueError("max_depth must be >= 0")
    if max_entries <= 0:
        raise ValueError("max_entries must be > 0")

    state = _WalkState()

    def walk(path: Path, depth: int) -> ProjectTreeEntry:
        kind = "directory" if path.is_dir() else "file"
        if kind == "directory":
            state.directories += 1
        else:
            state.files += 1
        state.emitted += 1
        if state.emitted >= max_entries:
            state.truncated = True
            children: tuple[ProjectTreeEntry, ...] = ()
        elif not path.is_dir() or depth >= max_depth:
            children = ()
        else:
            collected: list[ProjectTreeEntry] = []
            for child in _sorted_children(path, include_files=include_files):
                if _is_excluded(child, root=root_path, default_excludes=default_excludes, extra_excludes=extra_excludes):
                    state.skipped += 1
                    continue
                if state.truncated:
                    break
                collected.append(walk(child, depth + 1))
            children = tuple(collected)
        rel = "." if path == root_path else _normalize_rel(path.relative_to(root_path))
        return ProjectTreeEntry(path=rel, name=path.name or str(root_path), kind=kind, depth=depth, children=children)

    root_entry = walk(root_path, 0)
    summary = ProjectTreeSummary(
        root=str(root_path),
        directories=state.directories,
        files=state.files,
        skipped=state.skipped,
        truncated=state.truncated,
        max_depth=max_depth,
        include_files=include_files,
    )
    return ProjectTreeResult(root=root_entry, summary=summary)


def render_project_tree_text(result: ProjectTreeResult) -> str:
    lines: list[str] = [result.root.name]

    def render_children(children: Sequence[ProjectTreeEntry], prefix: str) -> None:
        for index, child in enumerate(children):
            is_last = index == len(children) - 1
            marker = "└── " if is_last else "├── "
            suffix = "/" if child.kind == "directory" else ""
            lines.append(f"{prefix}{marker}{child.name}{suffix}")
            child_prefix = f"{prefix}{'    ' if is_last else '│   '}"
            render_children(child.children, child_prefix)

    render_children(result.root.children, "")
    summary = result.summary
    lines.append("")
    lines.append(
        "summary: "
        f"directories={summary.directories} "
        f"files={summary.files} "
        f"skipped={summary.skipped} "
        f"max_depth={summary.max_depth} "
        f"truncated={summary.truncated}"
    )
    return "\n".join(lines) + "\n"


def render_project_tree_json(result: ProjectTreeResult) -> str:
    return json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render a clean, bounded repository tree.")
    parser.add_argument("root", nargs="?", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument("--max-depth", type=int, default=4, help="Maximum tree depth from root. Default: 4.")
    parser.add_argument("--max-entries", type=int, default=10_000, help="Maximum entries to emit before truncating. Default: 10000.")
    parser.add_argument("--dirs-only", action="store_true", help="Render directories only.")
    parser.add_argument("--no-default-excludes", action="store_true", help="Disable default runtime/build/cache excludes.")
    parser.add_argument("--exclude", action="append", default=(), help="Extra fnmatch exclude pattern. Can be repeated.")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format. Default: text.")
    parser.add_argument("--output", help="Optional file to write the result into.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    result = build_project_tree(
        args.root,
        max_depth=args.max_depth,
        include_files=not args.dirs_only,
        default_excludes=not args.no_default_excludes,
        extra_excludes=tuple(args.exclude or ()),
        max_entries=args.max_entries,
    )
    rendered = render_project_tree_json(result) if args.format == "json" else render_project_tree_text(result)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ProjectTreeEntry",
    "ProjectTreeResult",
    "ProjectTreeSummary",
    "build_project_tree",
    "main",
    "render_project_tree_json",
    "render_project_tree_text",
]
