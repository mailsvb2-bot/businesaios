from __future__ import annotations

from tests.arch._canon_boot_runtime_registry_guard import (
    BOOT_MARKER,
    audited_boot_entrypoints,
    has_marker,
    parse_file,
)


def test_boot_registry_public_entrypoints_have_markers() -> None:
    offenders: list[str] = []
    for path in audited_boot_entrypoints():
        parsed = parse_file(path)
        if not has_marker(parsed.tree, BOOT_MARKER):
            offenders.append(parsed.rel)
    assert not offenders, (
        "Public runtime boot entrypoints must declare CANON_BOOT_WIRING_ONLY = True. Offenders:\n- "
        + "\n- ".join(offenders)
    )
