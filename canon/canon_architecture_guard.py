from __future__ import annotations

from pathlib import Path

from tools.canon_audit.checks import run_operational_canon_checks

CRITICAL_PATHS = [
    "canon",
    "tools/canon_audit",
    "scripts/ci",
    "runtime/platform",
    "interfaces",
]

FORBIDDEN_SECOND_BRAIN_NAMES = [
    "decision_engine.py",
    "strategy_engine.py",
    "autonomous_ai.py",
    "ai_brain.py",
]


def _repo_root() -> Path:
    return Path.cwd()


def check_single_decision_core() -> None:
    # Backward-compatible presence check for legacy callers; operational Canon now
    # enforces the unique decision path via the audit registry and hard gates.
    if not (_repo_root() / "core").exists() and not (_repo_root() / "application").exists():
        raise RuntimeError("Canonical decision surface missing")


def check_second_brain() -> None:
    root = _repo_root()
    for path in root.rglob("*.py"):
        if path.name in FORBIDDEN_SECOND_BRAIN_NAMES:
            raise RuntimeError(f"Second brain detected: {path.relative_to(root).as_posix()}")


def check_infrastructure_layer() -> None:
    if not (_repo_root() / "runtime").exists():
        raise RuntimeError("Infrastructure layer missing")


def run_architecture_checks() -> bool:
    root = _repo_root()
    check_single_decision_core()
    check_second_brain()
    check_infrastructure_layer()
    report = run_operational_canon_checks(root)
    if not report.passed:
        summary = ", ".join(f"{v.code}:{v.subject}" for v in report.violations[:5])
        raise RuntimeError(
            "Operational Canon failed. "
            f"score={report.admission_score_100}; violations={len(report.violations)}; sample={summary}"
        )
    return True
