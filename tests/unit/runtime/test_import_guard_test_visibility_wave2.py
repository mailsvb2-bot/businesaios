from __future__ import annotations

from runtime.firewall.import_guard import _allow_forbidden


def test_import_guard_allows_runtime_internal_for_test_callers_only() -> None:
    assert _allow_forbidden("runtime._internal.effect_types", "test_sample") is True
    assert _allow_forbidden("runtime._internal.effect_types", "tests.runtime.test_sample") is True
    assert _allow_forbidden("runtime._internal.effect_types", "runtime.lazy_namespace") is True
    assert _allow_forbidden("runtime._internal.effect_types", "runtime.some_public_module") is False
