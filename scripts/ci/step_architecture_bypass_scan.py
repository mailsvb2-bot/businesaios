from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.ci.integrity import auditor
from scripts.ci.integrity.decision_authority_alias_scan import check_decision_authority_aliases


def _decision_authority_alias_guard() -> tuple[bool, str]:
    findings = check_decision_authority_aliases(auditor.iter_python_files(), auditor.load_spec())
    if not findings:
        return True, "decision authority alias scan passed"

    sample = " | ".join(
        f"{item.check_id}@{item.path}:{item.line}:{item.message}"
        for item in findings[:8]
    )
    if len(findings) > 8:
        sample += f" | {len(findings) - 8} more"
    return False, f"decision authority alias scan failed: {sample}"


def run() -> tuple[bool, str]:
    alias_ok, alias_message = _decision_authority_alias_guard()
    if not alias_ok:
        return False, alias_message

    root = Path.cwd()
    cmd = [sys.executable, "-m", "tools.architecture_bypass_scanner"]
    completed = subprocess.run(
        cmd,
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    output = ((completed.stdout or "") + (completed.stderr or "")).strip()
    if completed.returncode == 0:
        suffix = output or "architecture bypass scanner passed"
        return True, f"{alias_message}; {suffix}"
    message = output or "architecture bypass scanner failed"
    return False, message[:12000]
