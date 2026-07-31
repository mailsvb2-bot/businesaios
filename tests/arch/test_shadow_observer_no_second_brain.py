from __future__ import annotations

import ast
from pathlib import Path

from canon.anti_second_brain_rules import (
    CANONICAL_DECISION_CORE_PATH,
    CANONICAL_SHADOW_EVIDENCE_PATH,
    SHADOW_FORBIDDEN_AUTHORITY_METHODS,
    SHADOW_POLICY_MODULE_PREFIX,
)

ROOT = Path(__file__).resolve().parents[2]
SHADOW_PATH = CANONICAL_SHADOW_EVIDENCE_PATH
OWNER_PATH = CANONICAL_DECISION_CORE_PATH
CALLER_PATH = "application/decision_runtime/run.py"
ALLOWED_SHADOW_EVENTS = {
    "SHADOW_DECISION_EVALUATED",
    "SHADOW_PRODUCTION_OUTCOME_OBSERVED",
    "SHADOW_OUTCOME_ATTRIBUTED",
}
FORBIDDEN_IMPORT_ROOTS = {
    "boto3", "httpx", "infrastructure", "interfaces", "os", "pathlib", "psycopg",
    "redis", "requests", "runtime", "shutil", "smtplib", "socket", "sqlite3",
    "storage", "subprocess", "urllib",
}
FORBIDDEN_AUTHORITY_CALLS = set(SHADOW_FORBIDDEN_AUTHORITY_METHODS) | {"activate_bootstrap", "issue", "optimize", "register", "rollback_policy"}
FORBIDDEN_BUILTIN_CALLS = {"eval", "exec", "open", "__import__"}
FORBIDDEN_EFFECT_CALLS = {
    "commit", "connect", "delete", "enqueue", "flush", "open", "publish", "put",
    "remove", "request", "send", "unlink", "write", "write_bytes",
    "write_text",
}


def _tree(relative: str) -> ast.AST:
    return ast.parse((ROOT / relative).read_text(encoding="utf-8"), filename=relative)


def _imports(tree: ast.AST) -> set[str]:
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def _attribute_calls(tree: ast.AST) -> set[str]:
    return {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }


def test_shadow_module_is_evidence_only_by_static_contract() -> None:
    source = (ROOT / SHADOW_PATH).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=SHADOW_PATH)
    roots = {name.split(".", 1)[0] for name in _imports(tree)}
    calls = _attribute_calls(tree)
    names = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert "CANON_SHADOW_EVIDENCE_ONLY = True" in source
    assert roots.isdisjoint(FORBIDDEN_IMPORT_ROOTS)
    assert calls.isdisjoint(FORBIDDEN_AUTHORITY_CALLS | FORBIDDEN_EFFECT_CALLS)
    assert names.isdisjoint(FORBIDDEN_BUILTIN_CALLS)
    assert "DecisionEnvelope" not in source
    assert "RuntimeExecutor" not in source
    assert "PolicyRegistry" not in source


def test_shadow_ledger_can_emit_only_shadow_evidence_events() -> None:
    tree = _tree(SHADOW_PATH)
    emitted: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != "emit":
            continue
        event_kw = next((kw.value for kw in node.keywords if kw.arg == "event_type"), None)
        assert isinstance(event_kw, ast.Name), "shadow event type must be a canonical constant"
        emitted.add(event_kw.id)
    assert emitted == ALLOWED_SHADOW_EVENTS


def test_shadow_candidate_namespace_is_pure_and_cannot_reach_effects() -> None:
    offenders: list[str] = []
    for path in (ROOT / "core/policies").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        roots = {name.split(".", 1)[0] for name in _imports(tree)}
        calls = _attribute_calls(tree)
        names = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        bad_imports = roots & FORBIDDEN_IMPORT_ROOTS
        bad_calls = calls & FORBIDDEN_EFFECT_CALLS
        bad_names = names & FORBIDDEN_BUILTIN_CALLS
        if bad_imports or bad_calls or bad_names:
            offenders.append(f"{path.relative_to(ROOT)} imports={sorted(bad_imports)} calls={sorted(bad_calls | bad_names)}")
    assert not offenders, "candidate policy namespace can perform effects:\n" + "\n".join(offenders)


def test_decision_core_is_the_only_shadow_observation_owner() -> None:
    owner = (ROOT / OWNER_PATH).read_text(encoding="utf-8")
    caller = (ROOT / CALLER_PATH).read_text(encoding="utf-8")
    assert "CANON_SHADOW_OBSERVATION_OWNER = True" in owner
    assert "def observe_shadow(" in owner
    assert "self._shadow_observer" in owner
    assert "self._shadow_observer.observe(" in owner
    assert "core.dispatch_shadow(" in caller
    assert "_shadow_observer" not in caller

    direct_observer_callers: list[str] = []
    shadow_entry_callers: list[str] = []
    for path in ROOT.rglob("*.py"):
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith("tests/"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "_shadow_observer.observe(" in text:
            direct_observer_callers.append(relative)
        if ".dispatch_shadow(" in text:
            shadow_entry_callers.append(relative)
    assert direct_observer_callers == [OWNER_PATH]
    assert shadow_entry_callers == [CALLER_PATH]


def test_shadow_policy_selection_rejects_noncanonical_policy_objects() -> None:
    source = (ROOT / "core/policies/selector.py").read_text(encoding="utf-8")
    assert f'module.startswith("{SHADOW_POLICY_MODULE_PREFIX}")' in source
    assert "rollout_config()" in source
    assert "int(pct or 0) != 0" in source


def test_shadow_promotion_stays_inside_sealed_effect_path() -> None:
    policy_effects = (ROOT / "runtime/_internal/effects_actions/policy_actions.py").read_text(encoding="utf-8")
    registry = (ROOT / "core/ai/policy_registry.py").read_text(encoding="utf-8")
    assert "assert_called_from_executor()" in policy_effects
    assert "SHADOW_PROMOTION_BLOCKED" in policy_effects
    assert "RolloutGuard.allow_promotion" in policy_effects
    assert "assert_called_from_runtime_executor()" in registry
    assert "if pct > 0:" in registry
