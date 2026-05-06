from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def platform_support_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]
