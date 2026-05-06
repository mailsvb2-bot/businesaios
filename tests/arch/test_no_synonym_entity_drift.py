from __future__ import annotations

from tests.arch.rules.synonym_clusters import SYNONYM_CLUSTERS
from tests.arch.scanners.name_fragment_scanner import find_class_names
from tests.arch.scanners.python_file_loader import read_text


TARGET_FILES = (
    "runtime/decision_gateway.py",
    "runtime/integration/runtime_packet_provider.py",
)


def test_no_synonym_entity_drift_in_new_single_path_names() -> None:
    seen: dict[str, set[str]] = {key: set() for key in SYNONYM_CLUSTERS}

    for path_str in TARGET_FILES:
        for class_name in find_class_names(read_text(__import__('pathlib').Path(path_str))):
            lowered = class_name.lower()
            for cluster_name, terms in SYNONYM_CLUSTERS.items():
                matched = [term for term in terms if term in lowered]
                if matched:
                    seen[cluster_name].update(matched)

    violations = {cluster_name: sorted(values) for cluster_name, values in seen.items() if len(values) >= 3}
    assert not violations, f"synonym drift detected: {violations}"
