from __future__ import annotations

from tests.arch._canon_boot_runtime_registry_guard import (
    HANDLER_MARKER,
    audited_handler_entrypoints,
    has_marker,
    parse_file,
)


def test_handler_registry_public_entrypoints_have_markers() -> None:
    offenders: list[str] = []
    for path in audited_handler_entrypoints():
        parsed = parse_file(path)
        if not has_marker(parsed.tree, HANDLER_MARKER):
            offenders.append(parsed.rel)
    assert not offenders, "Public runtime handlers must declare CANON_THIN_HANDLER = True. Offenders:\n- " + "\n- ".join(offenders)
