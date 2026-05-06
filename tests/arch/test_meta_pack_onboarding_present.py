from __future__ import annotations
from tests.arch._canon_meta_pack_guard import ONBOARDING_PATH

def test_meta_pack_onboarding_present() -> None:
    assert ONBOARDING_PATH.exists(), "Missing docs/CANON_ONBOARDING_FOR_ARCHITECTS_V1.md"
