from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from bootstrap.world_model_forbidden_paths import (
    scan_repo_for_forbidden_world_model_paths,
)
from scripts.ci.integrity import auditor
from scripts.ci.integrity.decision_authority_alias_scan import (
    check_decision_authority_aliases,
)
from tools.decision_authority_indirect_scanner import (
    scan as scan_indirect_decision_authority,
)


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _decision_authority_alias_guard() -> tuple[bool, str]:
    findings = check_decision_authority_aliases(
        auditor.iter_python_files(),
        auditor.load_spec(),
    )
    if not findings:
        return True, "decision authority alias scan passed"

    sample = " | ".join(
        f"{item.check_id}@{item.path}:{item.line}:{item.message}"
        for item in findings[:8]
    )
    if len(findings) > 8:
        sample += f" | {len(findings) - 8} more"
    return False, f"decision authority alias scan failed: {sample}"


def _indirect_decision_authority_guard(
    repo_root: Path | None = None,
) -> tuple[bool, str]:
    root = (repo_root or _repository_root()).resolve()
    findings = scan_indirect_decision_authority(root)
    if not findings:
        return True, "indirect decision authority scan passed"

    sample = " | ".join(item.format() for item in findings[:8])
    if len(findings) > 8:
        sample += f" | {len(findings) - 8} more"
    return False, f"indirect decision authority scan failed: {sample}"


def _world_model_source_guard(
    repo_root: Path | None = None,
) -> tuple[bool, str]:
    root = (repo_root or _repository_root()).resolve()
    findings = scan_repo_for_forbidden_world_model_paths(repo_root=root)
    if not findings:
        return True, "world model source-path scan passed"

    sample = " | ".join(
        f"{item['pattern']}@{Path(item['path']).relative_to(root)}"
        for item in findings[:8]
    )
    if len(findings) > 8:
        sample += f" | {len(findings) - 8} more"
    return False, f"world model source-path scan failed: {sample}"


def run() -> tuple[bool, str]:
    alias_ok, alias_message = _decision_authority_alias_guard()
    if not alias_ok:
        return False, alias_message

    indirect_ok, indirect_message = _indirect_decision_authority_guard()
    if not indirect_ok:
        return False, indirect_message

    source_ok, source_message = _world_model_source_guard()
    if not source_ok:
        return False, source_message

    root = _repository_root()
    cmd = [sys.executable, "-m", "tools.architecture_bypass_scanner"]
    completed = subprocess.run(
        cmd,
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    output = (
        (completed.stdout or "") + (completed.stderr or "")
    ).strip()
    if completed.returncode == 0:
        suffix = output or "architecture bypass scanner passed"
        return True, (
            f"{alias_message}; {indirect_message}; "
            f"{source_message}; {suffix}"
        )
    message = output or "architecture bypass scanner failed"
    return False, message[:12000]
