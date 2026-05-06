from __future__ import annotations

import os


def test_tests_conftest_is_loaded():
    assert os.environ.get("BUSINESAIOS_TESTS_CONFTEST_LOADED") == "1", (
        "tests/conftest.py was not loaded. "
        "Ensure pytest discovers /tests and that conftest.py is located under /tests."
    )
