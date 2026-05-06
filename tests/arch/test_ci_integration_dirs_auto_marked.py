from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_integration_target_directories_have_local_marker_conftest() -> None:
    expected = [
        ROOT / "tests" / "integration" / "conftest.py",
        ROOT / "tests" / "runtime" / "conftest.py",
        ROOT / "tests" / "interfaces" / "conftest.py",
    ]
    missing = [str(path.relative_to(ROOT)) for path in expected if not path.exists()]
    assert not missing, f"missing integration marker conftest files: {missing}"
