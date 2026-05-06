from __future__ import annotations

"""CI dependency bootstrap only.

This surface may prepare Python packaging tools and test dependencies for CI,
but it must not define runtime gate order or construct the application/runtime.
"""

from pathlib import Path

from scripts.ci.paths import repo_root
from scripts.ci.subprocess_io import run_python

CANON_CI_BOOTSTRAP = True


def _install_requirements(path: Path) -> None:
    if path.exists():
        outcome = run_python(["-m", "pip", "install", "-r", str(path)])
        if outcome.returncode != 0:
            raise RuntimeError(f"dependency install failed for: {path}")


def main() -> int:
    outcome = run_python(["-m", "pip", "install", "--upgrade", "pip", "wheel", "setuptools"])
    if outcome.returncode != 0:
        raise RuntimeError("failed to upgrade base packaging tools")

    root = repo_root()
    _install_requirements(root / "requirements.txt")
    _install_requirements(root / "requirements.optional.txt")

    extras = [
        "pytest>=7,<9",
        "ruff>=0.6",
        "pytest-cov>=4,<7",
    ]
    outcome = run_python(["-m", "pip", "install", *extras])
    if outcome.returncode != 0:
        raise RuntimeError("failed to install CI extras")

    print("[ci] bootstrap completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
