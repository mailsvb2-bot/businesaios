from __future__ import annotations

from pathlib import Path

from canon.runtime_forbidden_raw_access import FORBIDDEN_RUNTIME_RAW_ACCESS_PATTERNS
from canon.runtime_risk_zones import RUNTIME_RISK_ZONE_PATH_FRAGMENTS


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_no_raw_runtime_gets_in_risk_zones() -> None:
    violations: list[str] = []

    for path in PROJECT_ROOT.rglob("*.py"):
        normalized = path.as_posix()

        if "boot/registrations/" in normalized:
            continue
        if "tests/" in normalized:
            continue
        if not _is_risk_zone(normalized):
            continue

        text = path.read_text(encoding="utf-8")

        for pattern in FORBIDDEN_RUNTIME_RAW_ACCESS_PATTERNS:
            if pattern in text:
                violations.append(f"{normalized}: contains forbidden pattern '{pattern}'")

    assert not violations, "\n".join(violations)


def _is_risk_zone(path_str: str) -> bool:
    return any(fragment in path_str for fragment in RUNTIME_RISK_ZONE_PATH_FRAGMENTS)
