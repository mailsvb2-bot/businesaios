from __future__ import annotations

from collections import defaultdict

from tests.arch.scanners.name_fragment_scanner import find_class_names
from tests.arch.scanners.python_file_loader import iter_python_files, read_text


ROLE_MARKERS = (
    "PacketProvider",
    "DecisionGateway",
    "DecisionInputService",
    "RuntimeStateEnrichmentService",
)


def test_no_duplicate_infra_roles_for_new_single_path_primitives() -> None:
    role_to_locations: dict[str, list[str]] = defaultdict(list)

    for path in iter_python_files():
        path_str = str(path).replace("\\", "/")
        if not path_str.startswith(("runtime/", "boot/", "tests/arch/")):
            continue
        text = read_text(path)
        for class_name in find_class_names(text):
            for marker in ROLE_MARKERS:
                if class_name == marker:
                    role_to_locations[class_name].append(path_str)

    duplicates = {role: locations for role, locations in role_to_locations.items() if len(locations) > 1}
    assert not duplicates, f"duplicate infra roles detected: {duplicates}"
