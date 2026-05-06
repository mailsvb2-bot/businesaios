from canon import (
    ALLOWED_SUBDIRS,
    BOOT_WIRING_LINE_LIMIT,
    CANON_DOMAIN_MARKER,
    DOMAIN_FILE_SYSTEM_VERSION,
    REQUIRED_ROOT_FILES,
    STRATEGIC_DOMAIN_NAMES,
    THIN_HANDLER_LINE_LIMIT,
    canon_domain_findings_as_dicts,
    scan_boot_wiring_only,
    scan_canon_domain_file_system,
    scan_thin_runtime_handlers,
)


def test_public_exports_include_domain_fs_contract() -> None:
    assert DOMAIN_FILE_SYSTEM_VERSION == "DFS-V1"
    assert CANON_DOMAIN_MARKER == "__canon_domain__.py"
    assert "world_model" in STRATEGIC_DOMAIN_NAMES
    assert "contracts.py" in REQUIRED_ROOT_FILES
    assert "builders" in ALLOWED_SUBDIRS
    assert THIN_HANDLER_LINE_LIMIT == 180
    assert BOOT_WIRING_LINE_LIMIT == 180
    assert callable(canon_domain_findings_as_dicts)
    assert callable(scan_canon_domain_file_system)
    assert callable(scan_thin_runtime_handlers)
    assert callable(scan_boot_wiring_only)
