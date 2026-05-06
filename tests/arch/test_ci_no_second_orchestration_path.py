from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "scripts" / "ci"
SENTINELS = [
    "assert-project-shape",
    "doctor-check",
    "quality-check",
    "canon-audit",
    "lock-tests",
    "unit-tests",
    "integration-tests",
    "verify-release",
    "build-artifact",
]


def test_plan_order_defined_only_once() -> None:
    offenders: list[str] = []
    for path in sorted(TARGET.rglob("*.py")):
        if path.name == "plan_registry.py":
            continue
        text = path.read_text(encoding="utf-8")
        hits = sum(1 for sentinel in SENTINELS if sentinel in text)
        if hits >= 3:
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"second orchestration path detected: {offenders}"
