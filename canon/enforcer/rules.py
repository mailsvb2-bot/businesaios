from __future__ import annotations

import re
from pathlib import Path
from collections.abc import Iterable, Sequence

REPO_ROOT = Path('.')
PY_DIRS_TO_SCAN = ["core", "runtime", "interfaces", "runtime.platform", "governance", "canon"]
CRITICAL_DIR_PREFIXES = ["core/ai", "runtime", "interfaces/ads", "interfaces/telegram", "runtime.platform/event_store", "runtime.platform/ledger", "governance"]
FORBIDDEN_IMPORT_PREFIXES_IN_CORE = ("requests", "httpx", "aiohttp", "subprocess")
FORBIDDEN_EFFECT_CALL_TAILS_IN_CORE = {"apply", "apply_plan", "post", "patch", "request", "popen"}
FORBIDDEN_DECISION_FUNCTION_NAMES_OUTSIDE_CORE = {"decide", "issue_decision", "choose_strategy", "choose_offer", "pick_best_action", "select_strategy", "select_offer", "rank_candidates", "optimize_strategy"}
FORBIDDEN_SECOND_BRAIN_FILE_HINTS = {"decision_engine.py", "ai_brain.py", "autonomous_decider.py", "strategy_engine.py"}
SYNONYM_NAMESPACE_PAIRS = [("core/user", "core/users"), ("core/policy", "core/policies"), ("runtime/read_models", "core/read_model"), ("runtime/observability", "runtime.platform/observability")]
CRITICAL_SILENT_FAIL_PATTERNS = ["except Exception:\n        pass", "except:\n        pass", "except Exception as e:\n        pass"]
MAGIC_NUMBER_RE = re.compile(r"\b\d+\.\d+\b")
BUSINESS_HINT_RE = re.compile(r"(threshold|multiplier|stop_loss|rollout|limit|discount|margin|cvr|ctr|roi|cac)", re.IGNORECASE)
GOD_MODULE_LINE_THRESHOLD = 900
GOD_MODULE_FUNC_THRESHOLD = 25
GOD_MODULE_IMPORT_THRESHOLD = 35
ALLOWED_EMPTY_FILES = {"__init__.py"}


def iter_py_files(root: Path = REPO_ROOT) -> Iterable[Path]:
    for folder in PY_DIRS_TO_SCAN:
        base = root / folder
        if not base.exists():
            continue
        yield from base.rglob("*.py")


def safe_read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def path_str(path: Path) -> str:
    return str(path).replace("\\", "/")


def is_under(rel_path: str, prefixes: Sequence[str]) -> bool:
    return any(rel_path == p or rel_path.startswith(f"{p}/") for p in prefixes)


def is_critical_path(rel_path: str) -> bool:
    return is_under(rel_path, CRITICAL_DIR_PREFIXES)


def nontrivial_py_count(path: Path) -> int:
    if not path.exists() or not path.is_dir():
        return 0
    return sum(1 for p in path.rglob("*.py") if p.name != "__init__.py")


def iter_todo_lines(text: str):
    for idx, line in enumerate(text.splitlines(), start=1):
        if "TODO" in line and not line.strip().startswith("# noqa"):
            yield idx
