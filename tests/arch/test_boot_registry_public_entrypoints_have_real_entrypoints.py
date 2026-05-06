from __future__ import annotations

from tests.arch._canon_boot_runtime_registry_guard import (
    BOOT_ENTRY_PREFIXES,
    audited_boot_entrypoints,
    has_function_with_prefix,
    parse_file,
)


def test_boot_registry_public_entrypoints_have_real_entrypoints() -> None:
    offenders: list[str] = []
    for path in audited_boot_entrypoints():
        parsed = parse_file(path)
        if not has_function_with_prefix(parsed.tree, BOOT_ENTRY_PREFIXES):
            offenders.append(parsed.rel)
    assert not offenders, (
        "Public runtime boot entrypoints must have real register_/wire_/bind_/assemble_/compose_/build_* functions. Offenders:\n- "
        + "\n- ".join(offenders)
    )
