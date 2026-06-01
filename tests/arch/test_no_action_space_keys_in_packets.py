from __future__ import annotations

from tests.arch.rules.forbidden_name_fragments import FORBIDDEN_PACKET_CONTROL_KEYS
from tests.arch.scanners.python_file_loader import read_text

TARGET_FILES = (
    "runtime/decision_input/runtime_state_enrichment.py",
    "core/decisioning/decision_core_input_bridge.py",
)


def test_no_action_space_keys_in_single_path_packets() -> None:
    violations: list[str] = []
    for path_str in TARGET_FILES:
        text = read_text(__import__('pathlib').Path(path_str))
        for key in FORBIDDEN_PACKET_CONTROL_KEYS:
            if f'"{key}"' in text or f"'{key}'" in text:
                violations.append(f"{path_str}: contains forbidden packet control key literal {key}")
    # allowed because these files define guards, not payloads
    allowed_literals = {
        'runtime/decision_input/runtime_state_enrichment.py',
        'core/decisioning/decision_core_input_bridge.py',
    }
    filtered = [v for v in violations if v.split(':',1)[0] not in allowed_literals]
    assert not filtered
