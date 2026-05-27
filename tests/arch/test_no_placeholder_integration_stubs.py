from __future__ import annotations

from tests.arch.scanners.python_file_loader import read_text

PLACEHOLDER_WORDS = (
    "todo",
    "stub",
    "placeholder",
    "mock integration",
    "fake integration",
)
TARGET_FILES = (
    "runtime/integration/runtime_packet_provider.py",
    "runtime/decision_input/runtime_state_enrichment.py",
    "runtime/decision_gateway.py",
)


def test_no_placeholder_integration_stubs_in_new_single_path_files() -> None:
    violations: list[str] = []
    for path_str in TARGET_FILES:
        lowered = read_text(__import__('pathlib').Path(path_str)).lower()
        if any(word in lowered for word in PLACEHOLDER_WORDS):
            violations.append(path_str)
    assert not violations, f"placeholder-like integration stubs detected: {violations}"
