import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CRITICAL_PATHS = [
    ROOT / "runtime/handlers",
    ROOT / "runtime/executor.py",
    ROOT / "runtime/guard.py",
    ROOT / "runtime.platform/event_store",
    ROOT / "interfaces/telegram/pipeline",
]
ALLOWLIST = {
    str(ROOT / "runtime/handlers/ads_rl_suggest.py"),
    str(ROOT / "runtime/handlers/ads_rl_train_tick.py"),
    str(ROOT / "runtime/handlers/behavior_graph.py"),
    str(ROOT / "runtime/executor.py"),
    str(ROOT / "runtime/platform/event_store/sqlite_user_state.py"),
    str(ROOT / "runtime/platform/event_store/sqlite_read_queries.py"),
}

def _iter_paths():
    for item in CRITICAL_PATHS:
        if item.is_file():
            yield item
        elif item.exists():
            yield from item.rglob("*.py")

def test_no_silent_pass():
    offenders = []
    for path in _iter_paths():
        text = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                for handler in node.handlers:
                    if len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass) and str(path) not in ALLOWLIST:
                        offenders.append(str(path))
    assert offenders == []
