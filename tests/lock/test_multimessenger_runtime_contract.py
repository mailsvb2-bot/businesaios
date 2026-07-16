from __future__ import annotations

import pytest

from scripts.ci.multimessenger_contract import (
    EXPECTED_CHANNELS,
    verify_multimessenger_runtime_contract,
)


@pytest.mark.lock
def test_complete_multimessenger_runtime_surface_is_locked() -> None:
    ok, message = verify_multimessenger_runtime_contract()

    assert ok, message
    assert len(EXPECTED_CHANNELS) == 14
