from __future__ import annotations

"""Fail-closed top-level dependency drift check.

The project intentionally keeps a small top-level dependency set. CI and Docker
install from requirements.lock.txt, so requirements.txt must not drift away from
that locked contract. This check is intentionally stdlib-only so it can run
before dependencies are installed.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS = ROOT / "requirements.txt"
LOCK = ROOT / "requirements.lock.txt"


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
    print(f"requirements lock is in sync ({len(locked)} top-level dependencies)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
