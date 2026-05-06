from boot.wiring.runtime_manifest_loader import load_runtime_manifest


def test_no_duplicate_service_names() -> None:
    manifest = load_runtime_manifest()
    names = [entry.service_name for entry in manifest]
    assert len(names) == len(set(names))
