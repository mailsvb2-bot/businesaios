from __future__ import annotations


def test_runtime_boot_system_builder_import_is_explicit_file_surface() -> None:
    from runtime.boot.system_builder import build_system

    assert callable(build_system)
    assert build_system.__module__ == "bootstrap.system_builder"
