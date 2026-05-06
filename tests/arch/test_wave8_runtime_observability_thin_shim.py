from __future__ import annotations

from pathlib import Path


def test_runtime_observability_compat_surface_is_explicit_thin_shim() -> None:
    source = Path("runtime/observability.py").read_text(encoding="utf-8")
    assert "CANON_RUNTIME_OBSERVABILITY_THIN_SHIM = True" in source
    assert "CANON_RUNTIME_OBSERVABILITY_EXPLICIT_EXPORTS_ONLY = True" in source
    assert "import *" not in source
