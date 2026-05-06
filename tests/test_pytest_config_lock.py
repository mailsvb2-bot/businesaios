from __future__ import annotations

import pathlib


def test_pytest_ini_exists() -> None:
    """Hard lock: repo must ship pytest.ini so CI is deterministic."""

    root = pathlib.Path(__file__).resolve().parents[1]
    assert (root / "pytest.ini").exists()
