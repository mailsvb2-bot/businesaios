from __future__ import annotations

import configparser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_pytest_ini_has_canonical_markers_and_strictness() -> None:
    path = ROOT / "pytest.ini"
    assert path.exists(), "pytest.ini must exist"

    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")

    assert parser.has_section("pytest"), "pytest.ini must have [pytest] section"
    addopts = parser.get("pytest", "addopts", fallback="")
    assert "--strict-markers" in addopts
    assert "--strict-config" in addopts

    markers = parser.get("pytest", "markers", fallback="")
    assert "asyncio:" in markers
    assert "gate:" in markers
    assert "lock:" in markers
    assert "slow:" in markers
    assert "integration:" in markers
    assert "arch:" in markers
