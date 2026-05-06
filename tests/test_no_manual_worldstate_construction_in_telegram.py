from __future__ import annotations

"""Lock test: forbid ad-hoc WorldState construction inside Telegram interface.

Canonical rule:
  events -> reducers -> (telegram compat overlays)

WorldStateV1 may only be constructed inside:
  interfaces/telegram/runtime/telegram_runtime_worldstate_builder.py

This prevents "alternative paths" where a future change bypasses reducers.
"""

import ast
import pathlib


ALLOWED_CONSTRUCTORS = {
    "interfaces/telegram/runtime/telegram_runtime_worldstate_builder.py",
}


def _repo_root() -> pathlib.Path:
    # tests/ lives at repo root
    return pathlib.Path(__file__).resolve().parent.parent


def _iter_py_files(base: pathlib.Path) -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for p in base.rglob("*.py"):
        # Skip caches, vendored artifacts, and tests.
        if "__pycache__" in p.parts:
            continue
        if "tests" in p.parts:
            continue
        out.append(p)
    return out


def _calls_worldstatev1(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id == "WorldStateV1":
                return True
            if isinstance(fn, ast.Attribute) and fn.attr == "WorldStateV1":
                return True
    return False


def test_no_manual_worldstate_construction_in_telegram_interface() -> None:
    root = _repo_root()
    tg = root / "interfaces" / "telegram"
    assert tg.exists(), "telegram interface folder not found"

    offenders: list[str] = []

    for path in _iter_py_files(tg):
        rel = path.relative_to(root).as_posix()
        if rel in ALLOWED_CONSTRUCTORS:
            continue

        try:
            txt = path.read_text(encoding="utf-8")
        except Exception:
            continue

        try:
            tree = ast.parse(txt)
        except SyntaxError:
            continue

        if _calls_worldstatev1(tree):
            offenders.append(rel)

    assert not offenders, (
        "Manual WorldStateV1 construction is forbidden inside interfaces/telegram. "
        "Use interfaces.telegram.runtime.telegram_runtime_worldstate_builder instead. "
        f"Offenders: {offenders}"
    )
