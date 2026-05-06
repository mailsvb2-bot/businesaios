import pytest

from runtime.firewall.process_guard import (
    require_effect_capability,
    set_effect_capability,
    clear_effect_capability,
    ProcessCapabilityError,
)


def test_effect_without_token_fails():
    with pytest.raises(ProcessCapabilityError):
        require_effect_capability("secret")


def test_wrong_token_fails():
    set_effect_capability("wrong")

    with pytest.raises(ProcessCapabilityError):
        require_effect_capability("correct")

    clear_effect_capability()


def test_correct_token_passes():
    set_effect_capability("ok")
    require_effect_capability("ok")
    clear_effect_capability()
