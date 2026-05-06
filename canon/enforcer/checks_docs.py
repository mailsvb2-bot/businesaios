from __future__ import annotations

from pathlib import Path

from canon.canon_world_model_integrity import scan_world_model_canon_contract
from canon.enforcer.rules import REPO_ROOT


def check_readme_and_contributing(report, root: Path = REPO_ROOT) -> None:
    required = [
        "docs/SYSTEM_TZ_CANONICAL.md",
        "docs/ARCHITECTURE_CANON_V20.md",
        "docs/CANON_MESSAGING_POLICY_V1.md",
        "CONTRIBUTING.md",
        "scripts/certify_repo.py",
        "scripts/check_world_model_integrity.py",
        "scripts/check_world_model_typing.py",
        "scripts/migrate_world_model_to_canonical.py",
    ]
    for rel in required:
        if not (root / rel).exists():
            report.add(severity="high", kind="missing-canon-enforcement-file", path=rel, line=None, message="Required canon enforcement file is missing.", hint="Restore docs/tests/certify/integrity files so future contributors must respect the canon.")


def check_super_canon_world_model_contract(report, root: Path = REPO_ROOT) -> None:
    findings = scan_world_model_canon_contract(root)
    for item in findings:
        severity = "high"
        if item.kind in {"missing-world-model-canon-file", "missing-decision-core", "missing-runtime-executor", "missing-boot-core-assembly", "forbidden-world-model-pattern"}:
            severity = "critical"
        report.add(severity=severity, kind=item.kind, path=item.path, line=None, message=item.message, hint="Restore single-brain world-model canon, pinning, replay, and boot integrity.")
