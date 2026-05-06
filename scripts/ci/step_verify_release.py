from __future__ import annotations

from scripts.ci.makefile_tools import has_make_target
from scripts.ci.paths import repo_root
from scripts.ci.subprocess_io import run_command, run_python


def _run_optional_make_target(name: str) -> tuple[bool, str]:
    if not has_make_target(name):
        return True, f"make target absent; skipped by contract: {name}"

    outcome = run_command(["make", name])
    if outcome.returncode != 0:
        return False, f"make target failed: {name}"
    return True, f"make target passed: {name}"


def _run_optional_project_release_script() -> tuple[bool, str]:
    root = repo_root()

    verify_release = root / "scripts" / "verify_release.sh"
    if verify_release.exists():
        outcome = run_command(["bash", str(verify_release)])
        if outcome.returncode != 0:
            return False, "verify_release.sh failed"
        return True, "verify_release.sh passed"

    package_release = root / "scripts" / "package_release.py"
    if package_release.exists():
        outcome = run_python(["scripts/package_release.py"])
        if outcome.returncode != 0:
            return False, "package_release.py failed"
        return True, "package_release.py passed"

    if has_make_target("regen-manifest"):
        outcome = run_command(["make", "regen-manifest"])
        if outcome.returncode != 0:
            return False, "make regen-manifest failed"
        return True, "make regen-manifest passed"

    return True, "project-specific release verification absent; skipped by contract"


def run() -> tuple[bool, str]:
    parts: list[str] = []

    ok_guard, msg_guard = _run_optional_make_target("ci-guard")
    parts.append(msg_guard)
    if not ok_guard:
        return False, "; ".join(parts)

    ok_locks, msg_locks = _run_optional_make_target("ci-locks")
    parts.append(msg_locks)
    if not ok_locks:
        return False, "; ".join(parts)

    ok_project, msg_project = _run_optional_project_release_script()
    parts.append(msg_project)
    if not ok_project:
        return False, "; ".join(parts)

    return True, "; ".join(parts)
