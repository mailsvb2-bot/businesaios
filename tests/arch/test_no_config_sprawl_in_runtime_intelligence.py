from __future__ import annotations

from pathlib import Path

from tests.arch.scanners.config_literal_scanner import suspicious_config_lines
from tests.arch.scanners.python_file_loader import read_text

TARGET_FILES = (
    "runtime/integration/world_state_integration_service.py",
    "runtime/integration/fallback_policy.py",
)
ALLOWED_CONFIG_FILES = {"runtime/integration/fallback_policy.py"}
ALLOWED_FRAGMENTS = ("fallback_policy", "TEST_FALLBACK_POLICY", "STRICT_FALLBACK_POLICY")


def test_no_config_sprawl_in_new_runtime_intelligence_paths() -> None:
    violations: list[str] = []
    for path_str in TARGET_FILES:
        if path_str in ALLOWED_CONFIG_FILES:
            continue
        suspicious = tuple(
            line
            for line in suspicious_config_lines(read_text(Path(path_str)))
            if not any(fragment in line for fragment in ALLOWED_FRAGMENTS)
        )
        if suspicious:
            violations.append(f"{path_str}: suspicious config literals {suspicious[:5]}")
    assert not violations, "config sprawl detected:\n" + "\n".join(violations)
