from __future__ import annotations

from pathlib import Path

from tests.arch.rules.forbidden_name_fragments import FORBIDDEN_DECISION_FRAGMENTS
from tests.arch.scanners.name_fragment_scanner import find_function_names
from tests.arch.scanners.python_file_loader import read_text

TARGET_FILES = (
    "runtime/integration/runtime_packet_provider.py",
    "runtime/decision_input/runtime_state_enrichment.py",
)


def test_no_hidden_routing_api_drift_in_new_non_gateway_files() -> None:
    violations: list[str] = []
    for path_str in TARGET_FILES:
        names = find_function_names(read_text(Path(path_str)))
        for name in names:
            if any(fragment in name for fragment in FORBIDDEN_DECISION_FRAGMENTS):
                violations.append(f"{path_str}: forbidden decision-like function name {name}")
    assert not violations, "hidden routing api drift detected:\n" + "\n".join(violations)
