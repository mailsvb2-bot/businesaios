from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ALLOWED_EXECUTE_FILES = {
    "boot/registrations/register_decision_core.py",
    "execution/action_dispatcher.py",
}


def test_no_new_raw_action_executor_execute_calls_escape_canonical_gate() -> None:
    violations: list[str] = []
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith("tests/"):
            continue
        text = path.read_text(encoding="utf-8")
        if "action_executor.execute(" not in text:
            continue
        if rel not in ALLOWED_EXECUTE_FILES:
            violations.append(rel)
    assert not violations, "Unexpected raw action_executor.execute(...) outside canonical files: " + ", ".join(violations)


def test_runtime_boot_observability_is_not_silent_or_partial() -> None:
    text = (ROOT / "boot" / "runtime_boot.py").read_text(encoding="utf-8")
    for required in ("event_bus", "metrics", "tracer", "decision_audit_log", "action_audit_log"):
        assert required in text
