from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = ("application", "core", "runtime", "billing")


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return f"{func.value.id}.{func.attr}"
    return ""


def test_external_process_calls_are_fail_closed() -> None:
    offenders: list[str] = []
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, SyntaxError):
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = _call_name(node)
                if name == "os.system":
                    offenders.append(f"{path.relative_to(ROOT).as_posix()}:{node.lineno}:os.system")
                    continue
                if name != "subprocess.run":
                    continue
                check_keywords = [kw for kw in node.keywords if kw.arg == "check"]
                if not check_keywords or not (
                    isinstance(check_keywords[0].value, ast.Constant)
                    and check_keywords[0].value.value is True
                ):
                    offenders.append(
                        f"{path.relative_to(ROOT).as_posix()}:{node.lineno}:subprocess.run_without_check_true"
                    )
    assert offenders == [], "External process calls must fail closed:\n" + "\n".join(offenders)
