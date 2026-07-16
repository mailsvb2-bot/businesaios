from __future__ import annotations

from pathlib import Path


def test_verify_release_passes_python_bin_to_make_helpers() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "scripts" / "ci" / "step_verify_release.py").read_text(encoding="utf-8")

    assert 'return {"PYTHON_BIN": sys.executable}' in source
    assert 'run_command(["make", name], env=_canonical_python_env())' in source
    assert 'env=_canonical_python_env(),' in source
