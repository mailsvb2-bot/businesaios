from __future__ import annotations
from tests.arch._canon_exception_registry_guard import load_registry

def test_exception_registry_is_loadable() -> None:
    load_registry()
