#!/usr/bin/env python3
"""Safe debt fixer for BusinessAIOS.

This helper intentionally fixes only conservative import-order debt: a module
docstring placed after imports/future imports. It never removes imports, never
edits workflow safety locks, and never changes runtime logic.

The default mode is deliberately small and bounded. Wider runs must pass
explicit paths and a larger max-change budget.
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "node_modules",
    "build",
    "dist",
    "artifacts",
}
DEFAULT_PATHS = (
    "runtime/queue",
    "runtime/security",
    "runtime/scheduler.py",
    "runtime/self_driving_scheduler.py",
    "runtime/wiring.py",
    "runtime/tenancy/__init__.py",
)


@dataclass(frozen=True)
class FixResult:
    path: str
    changed: bool
    reason: str


def normalize_target(raw: str) -> Path:
    path = (ROOT / raw).resolve()
    if ROOT not in path.parents and path != ROOT:
        raise ValueError(f"target escapes repo root: {raw}")
    return path


def iter_python_files(targets: Iterable[str]) -> Iterable[Path]:
    seen: set[Path] = set()
    for raw in targets:
        target = normalize_target(raw)
        candidates: Iterable[Path]
        if target.is_file():
            candidates = (target,)
        elif target.is_dir():
            candidates = target.rglob("*.py")
        else:
            continue
        for path in candidates:
            if path.suffix != ".py":
                continue
            rel_parts = path.relative_to(ROOT).parts
            if any(part in EXCLUDED_DIRS for part in rel_parts):
                continue
            if path in seen:
                continue
            seen.add(path)
            yield path


def is_string_expr(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(getattr(stmt, "value", None), ast.Constant)
        and isinstance(stmt.value.value, str)
    )


def has_real_module_docstring(tree: ast.Module) -> bool:
    return bool(tree.body and is_string_expr(tree.body[0]))


def choose_docstring_candidate(tree: ast.Module) -> ast.stmt | None:
    for stmt in tree.body[:10]:
        if is_string_expr(stmt):
            return stmt
    return None


def split_top_prefix(lines: list[str]) -> tuple[list[str], list[str]]:
    prefix: list[str] = []
    rest = list(lines)
    while rest:
        line = rest[0]
        if line.startswith("#!") or "coding" in line[:100] or line.lstrip().startswith("#"):
            prefix.append(rest.pop(0))
            continue
        break
    return prefix, rest


def move_docstring_to_top(path: Path, *, apply: bool) -> FixResult:
    rel = path.relative_to(ROOT).as_posix()
    original = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(original)
    except SyntaxError as exc:
        return FixResult(rel, False, f"syntax-error: {exc}")

    if has_real_module_docstring(tree):
        return FixResult(rel, False, "already-canonical")

    doc_stmt = choose_docstring_candidate(tree)
    if doc_stmt is None:
        return FixResult(rel, False, "no-top-level-docstring-candidate")

    start = doc_stmt.lineno
    end = getattr(doc_stmt, "end_lineno", start)
    if start <= 1 or start > 25:
        return FixResult(rel, False, "docstring-candidate-outside-safe-window")

    lines = original.splitlines(keepends=True)
    doc_block = lines[start - 1 : end]
    before = lines[: start - 1]
    after = lines[end:]

    while before and before[-1].strip() == "":
        before.pop()
    while after and after[0].strip() == "":
        after.pop(0)

    prefix, rest_before = split_top_prefix(before)
    new_lines = prefix + doc_block + ["\n"] + rest_before
    if rest_before and rest_before[-1].strip() != "":
        new_lines.append("\n")
    new_lines += after
    new_text = "".join(new_lines)

    if new_text == original:
        return FixResult(rel, False, "unchanged-after-rewrite")

    try:
        ast.parse(new_text)
    except SyntaxError as exc:
        return FixResult(rel, False, f"rewrite-would-break-syntax: {exc}")

    if apply:
        path.write_text(new_text, encoding="utf-8")
    return FixResult(rel, True, "moved-module-docstring-before-imports")


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    print("$", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report-dir", default="artifacts/github-debt-autopilot")
    parser.add_argument("--path", action="append", dest="paths", help="Path or directory to scan. Can be repeated.")
    parser.add_argument("--max-changes", type=int, default=30)
    args = parser.parse_args(argv)

    targets = tuple(args.paths or DEFAULT_PATHS)
    report_dir = ROOT / args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)

    py_files = list(iter_python_files(targets))
    if not py_files:
        print("python_files=0")
        return 0

    rel_files = [p.relative_to(ROOT).as_posix() for p in py_files]
    before = run([sys.executable, "-m", "ruff", "check", *rel_files, "--select", "E402,F401", "--output-format", "json"])
    (report_dir / "ruff-before.json").write_text(before.stdout, encoding="utf-8")

    planned_results = [move_docstring_to_top(path, apply=False) for path in py_files]
    planned_changed = [result for result in planned_results if result.changed]
    if len(planned_changed) > args.max_changes:
        write_json(report_dir / "docstring-fixes.json", [result.__dict__ for result in planned_results])
        print(f"python_files={len(py_files)}")
        print(f"planned_docstring_fixes={len(planned_changed)}")
        print(f"ERROR: planned changes exceed max_changes={args.max_changes}")
        return 2

    results = [move_docstring_to_top(path, apply=args.apply) for path in py_files]
    changed = [result for result in results if result.changed]
    write_json(report_dir / "docstring-fixes.json", [result.__dict__ for result in results])

    print(f"python_files={len(py_files)}")
    print(f"docstring_fixes={len(changed)}")
    for result in changed[:200]:
        print(f"fixed {result.path}: {result.reason}")

    if changed:
        compile_result = run([sys.executable, "-m", "compileall", "-q", *[result.path for result in changed]])
        (report_dir / "compileall-changed.log").write_text(compile_result.stdout, encoding="utf-8")
        if compile_result.returncode != 0:
            return compile_result.returncode

    after = run([sys.executable, "-m", "ruff", "check", *rel_files, "--select", "E402,F401", "--output-format", "json"])
    (report_dir / "ruff-after.json").write_text(after.stdout, encoding="utf-8")

    status = run(["git", "status", "--short"])
    (report_dir / "git-status.txt").write_text(status.stdout, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
