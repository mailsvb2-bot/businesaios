from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_no_ci_run_shell_orchestration_files_exist() -> None:
    ci_dir = ROOT / "ci"
    offenders: list[str] = []
    if ci_dir.exists():
        for path in sorted(ci_dir.glob("run_*.sh")):
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"unexpected shell orchestration files present: {offenders}"
