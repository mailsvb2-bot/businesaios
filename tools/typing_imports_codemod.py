from __future__ import annotations

"""Safe codemod for UP035-style typing imports.

This script rewrites deprecated ABC imports from `typing` to `collections.abc`.
It does not remove unused imports and does not touch E402/import ordering.

Use on a maintenance branch, then review the diff and run the normal full gates:

    python tools/typing_imports_codemod.py application

The transform is intentionally conservative and line-based. It only rewrites
simple `from typing import ...` lines and leaves all runtime logic untouched.
"""

import sys
from dataclasses import dataclass
from pathlib import Path

ABC_NAMES = {
    "AbstractSet",
    "AsyncContextManager",
    "AsyncGenerator",
    "AsyncIterable",
    "AsyncIterator",
    "Awaitable",
    "ByteString",
    "Callable",
    "ChainMap",
    "Collection",
    "Container",
    "ContextManager",
    "Coroutine",
    "Counter",
    "DefaultDict",
    "Deque",
    "Generator",
    "Hashable",
    "ItemsView",
    "Iterable",
    "Iterator",
    "KeysView",
    "Mapping",
    "MappingView",
    "MutableMapping",
    "MutableSequence",
    "MutableSet",
    "OrderedDict",
    "Reversible",
    "Sequence",
    "ValuesView",
}

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class FileChange:
    path: str
    moved: tuple[str, ...]


def _emit_stdout(message: str) -> None:
    sys.stdout.write(message + "\n")


def _emit_stderr(message: str) -> None:
    sys.stderr.write(message + "\n")


def _split_import_names(line: str) -> list[str] | None:
    prefix = "from typing import "
    if not line.startswith(prefix):
        return None
    tail = line[len(prefix) :].strip()
    if "(" in tail or ")" in tail or "#" in tail:
        return None
    return [part.strip() for part in tail.split(",") if part.strip()]


def _rewrite_text(text: str) -> tuple[str, tuple[str, ...]]:
    lines = text.splitlines(keepends=True)
    moved_total: list[str] = []
    out: list[str] = []
    for line in lines:
        newline = "\n" if line.endswith("\n") else ""
        body = line[:-1] if newline else line
        names = _split_import_names(body)
        if names is None:
            out.append(line)
            continue
        abc_names = [name for name in names if name in ABC_NAMES]
        typing_names = [name for name in names if name not in ABC_NAMES]
        if not abc_names:
            out.append(line)
            continue
        moved_total.extend(abc_names)
        if typing_names:
            out.append("from typing import " + ", ".join(typing_names) + newline)
        out.append("from collections.abc import " + ", ".join(abc_names) + newline)
    return "".join(out), tuple(sorted(set(moved_total)))


def _iter_python_files(scope: Path):
    if scope.is_file() and scope.suffix == ".py":
        yield scope
        return
    for path in scope.rglob("*.py"):
        if any(part in {".git", ".venv", "venv", "__pycache__"} for part in path.parts):
            continue
        yield path


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    scope_arg = args[0] if args else "application"
    scope = (REPO_ROOT / scope_arg).resolve()
    if REPO_ROOT not in scope.parents and scope != REPO_ROOT:
        _emit_stderr(f"scope escapes repository root: {scope_arg}")
        return 2
    if not scope.exists():
        _emit_stderr(f"scope does not exist: {scope_arg}")
        return 2
    changes: list[FileChange] = []
    for path in _iter_python_files(scope):
        original = path.read_text(encoding="utf-8")
        rewritten, moved = _rewrite_text(original)
        if rewritten == original:
            continue
        path.write_text(rewritten, encoding="utf-8")
        changes.append(FileChange(path=path.relative_to(REPO_ROOT).as_posix(), moved=moved))
    for change in changes:
        _emit_stdout(f"{change.path}: moved {', '.join(change.moved)}")
    _emit_stdout(f"changed_files={len(changes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
