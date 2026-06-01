from __future__ import annotations

import argparse
import difflib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

# Only rewrite extremely safe, single-line patterns.
# Goal: generate PR-ready diff, not magical refactors.


@dataclass(frozen=True)
class Patch:
    path: Path
    before: str
    after: str


def _iter_py_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*.py"):
        parts = set(p.parts)
        if any(d in parts for d in EXCLUDE_DIRS):
            continue
        yield p


EMIT_RE = re.compile(
    r"""(?P<prefix>\b(?:self\.)?event_log\.)emit\(\s*event_type=(?P<etype>[^,]+),\s*source=(?P<src>[^,]+),\s*user_id=(?P<uid>[^,]+),\s*payload=(?P<payload>[^\)]+)\)"""
)


def _rewrite_line(line: str) -> str | None:
    # Replace: event_log.emit(event_type=..., source=..., user_id=..., payload=...)
    # With:    event_log.emit_for(ctx=ctx, event_type=..., source=..., user_id=..., payload=...)
    # Only if line already contains a visible ctx variable (common in policies/routers).
    if "ctx" not in line:
        return None
    m = EMIT_RE.search(line)
    if not m:
        return None
    repl = f"{m.group('prefix')}emit_for(ctx=ctx, event_type={m.group('etype')}, source={m.group('src')}, user_id={m.group('uid')}, payload={m.group('payload')})"
    return EMIT_RE.sub(repl, line)


def plan_patches(root: Path) -> list[Patch]:
    patches: list[Patch] = []
    for f in _iter_py_files(root):
        try:
            before = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        lines = before.splitlines(True)
        changed = False
        out: list[str] = []
        for line in lines:
            new_line = _rewrite_line(line)
            if new_line is not None and new_line != line:
                out.append(new_line)
                changed = True
            else:
                out.append(line)
        if changed:
            after = "".join(out)
            patches.append(Patch(f, before, after))
    return patches


def render_unified_diff(p: Patch, root: Path) -> str:
    rel = p.path.relative_to(root).as_posix()
    return "".join(
        difflib.unified_diff(
            p.before.splitlines(True),
            p.after.splitlines(True),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
        )
    )


def apply_patches(patches: list[Patch]) -> None:
    for p in patches:
        p.path.write_text(p.after, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="repo root")
    ap.add_argument("--apply", action="store_true", help="apply safe rewrites in-place")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    patches = plan_patches(root)
    if not patches:
        print("No safe rewrites found.")
        return
    diff = []
    for p in patches:
        diff.append(render_unified_diff(p, root))
    print("\n".join(diff).rstrip())
    if args.apply:
        apply_patches(patches)


if __name__ == "__main__":
    main()
