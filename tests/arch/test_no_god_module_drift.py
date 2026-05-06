from __future__ import annotations

from pathlib import Path

from tests.arch.rules.god_module_thresholds import (
    MAX_CLASS_METHODS_FOR_INFRA_PRIMITIVE,
    MAX_FILE_SIZE_LINES_FOR_INFRA_PRIMITIVE,
    MAX_IMPORT_LINES_PER_FILE,
)
from tests.arch.scanners.file_size_scanner import line_count
from tests.arch.scanners.import_scanner import count_import_lines
from tests.arch.scanners.public_method_scanner import count_public_methods
from tests.arch.scanners.python_file_loader import read_text


TARGET_FILES = (
    "runtime/integration/runtime_packet_provider.py",
    "runtime/decision_gateway.py",
    "runtime/decision_input/runtime_state_enrichment.py",
)


def test_no_god_module_drift_for_new_single_path_files() -> None:
    violations: list[str] = []
    for path_str in TARGET_FILES:
        text = read_text(Path(path_str))
        if count_import_lines(text) > MAX_IMPORT_LINES_PER_FILE:
            violations.append(f"{path_str}: too many import lines")
        if line_count(text) > MAX_FILE_SIZE_LINES_FOR_INFRA_PRIMITIVE:
            violations.append(f"{path_str}: file too large")
        for class_name, method_count in count_public_methods(text).items():
            if method_count > MAX_CLASS_METHODS_FOR_INFRA_PRIMITIVE:
                violations.append(f"{path_str}:{class_name}: too many public methods ({method_count})")
    assert not violations, "god-module drift detected:\n" + "\n".join(violations)
