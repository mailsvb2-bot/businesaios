from boot.wiring.runtime_manifest_loader import load_runtime_manifest


def test_all_registration_modules_are_under_boot_registrations() -> None:
    manifest = load_runtime_manifest()
    for entry in manifest:
        assert entry.module_path.startswith("boot.registrations.")
        assert entry.callable_name.startswith("register_")
