from boot.wiring.runtime_manifest_loader import load_runtime_manifest
from canon.runtime_service_publication_rules import ALLOWED_RUNTIME_SERVICE_NAMES


def test_no_unknown_runtime_service_names() -> None:
    manifest = load_runtime_manifest()
    manifest_names = {entry.service_name for entry in manifest}

    unknown = manifest_names - ALLOWED_RUNTIME_SERVICE_NAMES
    assert not unknown, f"Unknown runtime service names detected: {sorted(unknown)}"
