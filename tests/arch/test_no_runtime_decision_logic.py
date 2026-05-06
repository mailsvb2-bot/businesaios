import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = ["choose_strategy", "decide_", "optimize_"]

def _module_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")

def test_runtime_handlers_no_decision_logic():
    for path in (ROOT / "runtime/handlers").rglob("*.py"):
        text = _module_text(path)
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name
                for word in FORBIDDEN:
                    assert word not in name, f"Decision logic in runtime handler: {path}:{name}"

def test_runtime_handlers_do_not_define_decide_methods():
    offenders = []
    for path in (ROOT / "runtime/handlers").rglob("*.py"):
        text = _module_text(path)
        if "def decide(" in text:
            offenders.append(str(path))
    assert offenders == []
