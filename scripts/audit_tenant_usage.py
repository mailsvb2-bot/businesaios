from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterable

EXCLUDE_DIRS = {
    '.git', '.venv', 'venv', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache',
    'build', 'dist', 'artifacts',
}

# Low-level modules that are allowed to touch the raw EventStore contract directly.
RAW_EVENTSTORE_APPEND_ALLOWLIST = {
    'core/events/log_store.py',
    'core/knowledge/repositories/event_store_codec.py',
    'runtime/boot/boot_observability.py',
    'bootstrap/boot_observability.py',
    'runtime/platform/event_store/memory_event_store.py',
    'runtime/platform/event_store/sqlite_event_store_write_api.py',
}

# Transitional adapters that must tolerate non-canonical stores during cleanup.
RAW_EVENTSTORE_READ_ALLOWLIST = {
    'runtime/messaging_policy_trace/search_store.py',
}

SKIP_PREFIXES = (
    'tests/',
    'docs/',
    'examples/',
)


@dataclass(frozen=True)
class Violation:
    path: str
    lineno: int
    kind: str
    detail: str


class _TenantAudit(ast.NodeVisitor):
    def __init__(self, *, relpath: str, source: str) -> None:
        self.relpath = relpath
        self.source = source
        self.violations: list[Violation] = []

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        func = node.func
        if isinstance(func, ast.Attribute):
            attr = str(func.attr)
            base = self._base_name(func.value)
            keywords = {kw.arg for kw in node.keywords if kw.arg}

            if attr == 'append_event' and 'tenant_id' not in keywords:
                if self.relpath not in RAW_EVENTSTORE_APPEND_ALLOWLIST and self._looks_like_event_store_base(base):
                    self._add(node, 'raw_append_event', f'{base}.append_event(...) without strict tenant_id=')

            if attr in {'iter_events', 'count_events'} and 'tenant_id' not in keywords:
                if self.relpath not in RAW_EVENTSTORE_READ_ALLOWLIST and self._looks_like_event_store_base(base):
                    self._add(node, 'raw_iter_events', f'{base}.{attr}(...) without tenant_id=')

        self.generic_visit(node)

    def _add(self, node: ast.AST, kind: str, detail: str) -> None:
        self.violations.append(Violation(self.relpath, int(getattr(node, 'lineno', 0) or 0), kind, detail))

    @staticmethod
    def _looks_like_event_store_base(base: str) -> bool:
        lowered = base.lower()
        return (
            lowered.endswith('event_store')
            or 'event_store.' in lowered
            or lowered.endswith('.store')
            or lowered == 'store'
            or lowered.endswith('_store')
        )

    @staticmethod
    def _base_name(node: ast.AST) -> str:
        try:
            return ast.unparse(node)
        except Exception:
            if isinstance(node, ast.Name):
                return node.id
            if isinstance(node, ast.Attribute):
                return node.attr
            return '<expr>'


def _iter_py_files(root: Path) -> Iterable[Path]:
    for path in root.rglob('*.py'):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(SKIP_PREFIXES):
            continue
        parts = set(path.parts)
        if parts & EXCLUDE_DIRS:
            continue
        yield path


def audit(root: str | Path = '.') -> int:
    repo_root = Path(root).resolve()
    violations: list[Violation] = []

    for path in _iter_py_files(repo_root):
        rel = path.relative_to(repo_root).as_posix()
        try:
            source = path.read_text(encoding='utf-8')
            tree = ast.parse(source, filename=rel)
        except SyntaxError:
            # Syntax validation belongs to compile/test gates, not this tenant-specific audit.
            continue
        visitor = _TenantAudit(relpath=rel, source=source)
        visitor.visit(tree)
        violations.extend(visitor.violations)

    if violations:
        for item in sorted(violations, key=lambda v: (v.path, v.lineno, v.kind)):
            print(f'{item.path}:{item.lineno}: {item.kind}: {item.detail}')
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='Audit repo for legacy tenant-unsafe EventStore call shapes.')
    parser.add_argument('--root', default='.', help='repository root')
    args = parser.parse_args()
    return audit(args.root)


if __name__ == '__main__':
    raise SystemExit(main())
