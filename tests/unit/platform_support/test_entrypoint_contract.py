from __future__ import annotations

import pytest

from runtime.platform.support.cli._main_stub import CLI_ENTRYPOINT, cli_main
from runtime.platform.support.entrypoint_contract import build_entrypoint_spec, dispatch_entrypoint
from runtime.platform.support.scripts._main_stub import SCRIPT_ENTRYPOINT, script_main


def test_build_entrypoint_spec_is_stable() -> None:
    spec = build_entrypoint_spec(surface_label="CLI", audit_surface="cli", commands=("train", "rollout"))
    assert spec.surface_label == "CLI"
    assert spec.audit_surface == "cli"
    assert spec.commands == ("train", "rollout")


def test_dispatch_entrypoint_rejects_unknown_command() -> None:
    spec = build_entrypoint_spec(surface_label="script", audit_surface="script", commands=("rebuild_lineage",))
    with pytest.raises(RuntimeError):
        dispatch_entrypoint("missing", spec=spec)


def test_cli_and_script_entrypoints_are_canonical_specs() -> None:
    assert CLI_ENTRYPOINT.surface_label == "CLI"
    assert CLI_ENTRYPOINT.audit_surface == "cli"
    assert "train" in CLI_ENTRYPOINT.commands
    assert SCRIPT_ENTRYPOINT.surface_label == "script"
    assert SCRIPT_ENTRYPOINT.audit_surface == "script"
    assert "rebuild_lineage" in SCRIPT_ENTRYPOINT.commands


def test_cli_main_routes_known_command(monkeypatch) -> None:
    monkeypatch.setattr(
        "runtime.platform.support.entrypoint_contract.run_named_command",
        lambda *, surface, command, implementations=None: 11 if surface == "cli" and command == "train" else 0,
    )
    assert cli_main("train") == 11


def test_script_main_routes_known_command(monkeypatch) -> None:
    monkeypatch.setattr(
        "runtime.platform.support.entrypoint_contract.run_named_command",
        lambda *, surface, command, implementations=None: 13 if surface == "script" and command == "rebuild_lineage" else 0,
    )
    assert script_main("rebuild_lineage") == 13
