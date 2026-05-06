from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

from scripts.ci.config import project_shape_config
from scripts.ci.paths import repo_root
from scripts.ci.subprocess_io import run_python


def _iter_python_files(path: Path):
    if path.is_file() and path.suffix == ".py":
        yield path
        return
    if not path.exists():
        return
    for candidate in path.rglob("*.py"):
        parts = set(candidate.parts)
        if "__pycache__" in parts or ".venv" in parts or "venv" in parts:
            continue
        yield candidate


def _syntax_check_targets() -> tuple[bool, str]:
    root = repo_root()
    cfg = project_shape_config(root)

    if not cfg.quality_targets:
        return False, "quality target set is empty"

    failed: list[str] = []
    checked = 0
    for rel in cfg.quality_targets:
        for path in _iter_python_files(root / rel):
            checked += 1
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError as exc:
                failed.append(f"{path.relative_to(root)}:{exc.lineno}:{exc.offset}: {exc.msg}")
            except UnicodeDecodeError as exc:
                failed.append(f"{path.relative_to(root)}: unicode decode error: {exc}")

    if failed:
        return False, "syntax check failed: " + "; ".join(failed[:20])

    return True, f"syntax check passed for {checked} Python files"


def _ruff_check() -> tuple[bool, str]:
    root = repo_root()
    target = root / "scripts" / "ci"
    config = root / "ruff.toml"
    if not target.exists():
        return False, "scripts/ci missing"
    if importlib.util.find_spec("ruff") is None:
        return True, "ruff unavailable in environment; skipped by contract"

    args = ["-m", "ruff", "check", str(target)]
    if config.exists():
        args.extend(["--config", str(config)])

    outcome = run_python(args, timeout=60)
    if outcome.returncode != 0:
        return False, "ruff check failed"

    return True, "ruff check passed"


def run() -> tuple[bool, str]:
    ok_syntax, msg_syntax = _syntax_check_targets()
    if not ok_syntax:
        return False, msg_syntax

    ok_ruff, msg_ruff = _ruff_check()
    if not ok_ruff:
        return False, msg_ruff

    return True, f"{msg_syntax}; {msg_ruff}"
