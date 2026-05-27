from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass
from typing import Iterable, Iterator, Pattern

# Small infra primitive:
# - repo-wide scanning by line regex
# - no AST magic, no “god objects”, no coupling to project internals

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Hit:
    relpath: str
    lineno: int
    line: str
    rule: str


def iter_py_files(*, root: pathlib.Path = REPO_ROOT) -> Iterator[pathlib.Path]:
    for p in root.rglob("*.py"):
        if any(part in {".venv", "venv", "__pycache__", ".pytest_cache"} for part in p.parts):
            continue
        yield p


def to_relpath(p: pathlib.Path, *, root: pathlib.Path = REPO_ROOT) -> str:
    try:
        return p.relative_to(root).as_posix()
    except Exception:
        return p.as_posix()


def _glob_to_regex(glob: str) -> Pattern[str]:
    # Minimal glob -> regex:
    #   **  => .* (including /)
    #   *   => [^/]* (excluding /)
    esc = re.escape(glob)
    esc = esc.replace(r"\*\*", "§§DS§§")
    esc = esc.replace(r"\*", "§§S§§")
    esc = esc.replace("§§DS§§", r".*")
    esc = esc.replace("§§S§§", r"[^/]*")
    return re.compile(r"^" + esc + r"$")


def scan_lines(
    *,
    patterns: dict[str, str],
    include_glob: str | None = None,
    exclude_glob: str | None = None,
    allowlist_relpaths: Iterable[str] = (),
    root: pathlib.Path = REPO_ROOT,
) -> list[Hit]:
    allow = set(allowlist_relpaths)
    include_re = _glob_to_regex(include_glob) if include_glob else None
    exclude_re = _glob_to_regex(exclude_glob) if exclude_glob else None

    compiled: list[tuple[str, Pattern[str]]] = [(name, re.compile(rx)) for name, rx in patterns.items()]
    hits: list[Hit] = []

    for p in iter_py_files(root=root):
        rel = to_relpath(p, root=root)
        if rel in allow:
            continue
        if include_re and not include_re.search(rel):
            continue
        if exclude_re and exclude_re.search(rel):
            continue

        text = p.read_text(encoding="utf-8", errors="replace").splitlines()
        for i, line in enumerate(text, start=1):
            for rule, rx in compiled:
                if rx.search(line):
                    hits.append(Hit(relpath=rel, lineno=i, line=line.rstrip("\n"), rule=rule))
    return hits


def format_hits(hits: list[Hit], *, limit: int = 80) -> str:
    if not hits:
        return ""
    out: list[str] = []
    for h in hits[:limit]:
        out.append(f"{h.relpath}:{h.lineno}: {h.line}   [rule: {h.rule}]")
    if len(hits) > limit:
        out.append(f"... and {len(hits) - limit} more")
    return "\n".join(out)
