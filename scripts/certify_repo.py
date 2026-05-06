"""Repo certification for BusinesAIOS.

Goals
- Keep architecture boundaries enforceable with a cheap, fast, stdlib-only gate.
- Warn-only by default for developer friendliness.
- Strict in CI to prevent drift.

Strict mode can be enabled via:
- CLI: --strict
- ENV: BUSINESAIOS_CERT_STRICT=1

Design notes
- Hermetic: stdlib only.
- Conservative: fail only on clear violations.
- "Signals" are informational diagnostics that never fail CI.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

from runtime.platform.config.env_flags import env_bool

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from canon.canon_ai_enforcer import run_enforcer

from scripts.certify_helpers import (
    TRUTHY,
    CertificationReport,
    analyze_god_objects_and_complexity,
    check_god_modules,
    detect_policy_divergence_signals,
    find_network_imports_outside_sealed,
)




def prune_generated_release_artifacts(root: Path) -> None:
    for p in list(root.rglob("__pycache__")):
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
    for p in list(root.rglob("*.pyc")):
        p.unlink(missing_ok=True)

def find_forbidden_release_artifacts(root: Path) -> list[str]:
    bad: list[str] = []
    for p in root.rglob("*"):
        if not p.exists():
            continue
        rel = p.relative_to(root).as_posix()
        if "__pycache__" in p.parts:
            bad.append(rel)
        elif p.suffix == ".pyc":
            bad.append(rel)
        elif rel.startswith("runtime/data/demo/") and p.suffix == ".db":
            bad.append(rel)
        elif rel.startswith("runtime/data/test/") and p.suffix == ".db":
            bad.append(rel)
    return bad


def certify_repo(root: str | Path) -> CertificationReport:
    r = Path(root).resolve()
    prune_generated_release_artifacts(r)
    report = CertificationReport()

    for file, lib in find_network_imports_outside_sealed(r):
        report.violations.append(
            f"forbidden network import outside runtime/_internal: {lib} in {file}"
        )

    for rel in find_forbidden_release_artifacts(r):
        report.violations.append(f"forbidden release artifact: {rel}")

    report.warnings.extend(check_god_modules(r))

    w2, s2 = analyze_god_objects_and_complexity(r)
    report.warnings.extend(w2)
    report.signals.extend(s2)
    report.signals.extend(detect_policy_divergence_signals(r))

    return report


def fail(msg: str) -> None:
    print("CERTIFICATION FAILED:", msg)
    raise SystemExit(1)


def check_empty_files() -> None:
    for root, _, files in os.walk("."):
        for f in files:
            path = os.path.join(root, f)
            if os.path.getsize(path) == 0 and not f.startswith("__init__"):
                fail(f"Empty file detected: {path}")


def check_duplicate_layers() -> None:
    if os.path.exists("core/user") and os.path.exists("core/users"):
        fail("Duplicate user namespaces")


def check_decision_core() -> None:
    if not os.path.exists("core/ai/decision_core.py"):
        fail("DecisionCore missing")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--strict", action="store_true", help="Fail on any certification warning")
    args = parser.parse_args()

    strict_env = env_bool("BUSINESAIOS_CERT_STRICT", False)
    strict = bool(args.strict or strict_env)

    report = certify_repo(args.root)
    print(report.render_text())

    prune_generated_release_artifacts(Path(args.root).resolve())
    enforcer_report = run_enforcer(".")
    prune_generated_release_artifacts(Path(args.root).resolve())
    if not enforcer_report.ok:
        fail("canon_ai_enforcer detected high/critical violations")

    if not report.ok:
        return 2
    if strict and report.warnings:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
