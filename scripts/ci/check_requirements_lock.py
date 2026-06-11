from __future__ import annotations

import os
from pathlib import Path

"""Fail-closed dependency lock contract.

The lightweight default check preserves the historical top-level drift guard.
Release/pre-release gates additionally require the lock file to represent a real
transitive lock. A top-level-only lock is useful for development consistency, but
it is not enough evidence for production reproducibility.
"""


ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS = ROOT / "requirements.txt"
LOCK = ROOT / "requirements.lock.txt"

_TOP_LEVEL_ONLY_MARKERS = (
    "Locked top-level dependencies",
    "Transitive dependency locking can be added later",
    "top-level dependency set",
)


def _normalized_lines(path: Path) -> set[str]:
    if not path.exists():
        raise FileNotFoundError(path)
    items: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Keep extras and pins exact, but ignore inline comments.
        if " #" in line:
            line = line.split(" #", 1)[0].strip()
        items.add(line)
    return items


def _release_lock_required() -> bool:
    return str(os.getenv("BAIOS_REQUIRE_TRANSITIVE_DEPENDENCY_LOCK") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "release",
        "required",
    }


def _lock_is_top_level_only(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    return any(marker in text for marker in _TOP_LEVEL_ONLY_MARKERS)


def main() -> int:
    requirements = _normalized_lines(REQUIREMENTS)
    locked = _normalized_lines(LOCK)
    missing_from_lock = sorted(requirements - locked)
    extra_in_lock = sorted(locked - requirements)
    if missing_from_lock or extra_in_lock:
        print("requirements lock drift detected")
        if missing_from_lock:
            print("missing_from_lock:")
            for item in missing_from_lock:
                print(f"  - {item}")
        if extra_in_lock:
            print("extra_in_lock:")
            for item in extra_in_lock:
                print(f"  - {item}")
        return 1
    if _release_lock_required() and _lock_is_top_level_only(LOCK):
        print("requirements lock is top-level-only; release requires a transitive lock")
        print("regenerate requirements.lock.txt with pip-tools/uv/poetry and remove top-level-only markers")
        return 1
    print(f"requirements lock is in sync ({len(locked)} top-level dependencies)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
