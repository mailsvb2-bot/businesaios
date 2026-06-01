from __future__ import annotations

from tests.arch._canon_boot_runtime_registry_guard import (
    HANDLER_ENTRY_PREFIXES,
    audited_handler_entrypoints,
    has_function_with_prefix,
    parse_file,
)


def test_handler_registry_public_entrypoints_have_real_entrypoints() -> None:
    offenders: list[str] = []
    for path in audited_handler_entrypoints():
        parsed = parse_file(path)
        if not has_function_with_prefix(parsed.tree, HANDLER_ENTRY_PREFIXES):
            offenders.append(parsed.rel)
    assert not offenders, "Public runtime handlers must have real handle_* entrypoints. Offenders:\n- " + "\n- ".join(offenders)
