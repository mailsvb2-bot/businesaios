from __future__ import annotations

import pytest

from runtime.platform.support.command_registry import normalize_command_name, require_known_command
from runtime.platform.support.cli.registry import CLI_COMMANDS
from runtime.platform.support.scripts.registry import SCRIPT_COMMANDS


def test_normalize_command_name_hyphen_to_underscore() -> None:
    assert normalize_command_name("rebuild-lineage") == "rebuild_lineage"


def test_require_known_command_accepts_registered_cli_name() -> None:
    assert require_known_command("train", commands=CLI_COMMANDS, surface="CLI") == "train"


def test_require_known_command_rejects_empty_script_name() -> None:
    with pytest.raises(RuntimeError):
        require_known_command("", commands=SCRIPT_COMMANDS, surface="script")
