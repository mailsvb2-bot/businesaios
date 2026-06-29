"""Canonical platform-support CLI surface with synthetic compatibility submodules."""

from __future__ import annotations


from runtime.platform.support.cli._main_stub import cli_main
from runtime.platform.support.cli.commands import build_cli_implementations
from runtime.platform.support.cli.registry import CLI_COMMANDS, is_known_cli_command

CLI_ENTRYPOINT = cli_main

def audit_main() -> int:
    return cli_main("audit")

def checkpoints_main() -> int:
    return cli_main("checkpoints")

def datasets_main() -> int:
    return cli_main("datasets")

def evaluate_main() -> int:
    return cli_main("evaluate")

def experiments_main() -> int:
    return cli_main("experiments")

def governance_main() -> int:
    return cli_main("governance")

def inspect_main() -> int:
    return cli_main("inspect")

def lineage_main() -> int:
    return cli_main("lineage")

def main() -> int:
    return cli_main("main")

def promote_main() -> int:
    return cli_main("promote")

def rollback_main() -> int:
    return cli_main("rollback")

def rollout_main() -> int:
    return cli_main("rollout")

def train_main() -> int:
    return cli_main("train")

_CLI_COMPAT_EXPORTS = {
    "audit": {"main": f"{__name__}:audit_main"},
    "checkpoints": {"main": f"{__name__}:checkpoints_main"},
    "datasets": {"main": f"{__name__}:datasets_main"},
    "evaluate": {"main": f"{__name__}:evaluate_main"},
    "experiments": {"main": f"{__name__}:experiments_main"},
    "governance": {"main": f"{__name__}:governance_main"},
    "inspect": {"main": f"{__name__}:inspect_main"},
    "lineage": {"main": f"{__name__}:lineage_main"},
    "main": {"main": f"{__name__}:main"},
    "promote": {"main": f"{__name__}:promote_main"},
    "rollback": {"main": f"{__name__}:rollback_main"},
    "rollout": {"main": f"{__name__}:rollout_main"},
    "train": {"main": f"{__name__}:train_main"},
}

__all__ = [
    "CLI_COMMANDS",
    "CLI_ENTRYPOINT",
    "audit_main",
    "build_cli_implementations",
    "checkpoints_main",
    "cli_main",
    "datasets_main",
    "evaluate_main",
    "experiments_main",
    "governance_main",
    "inspect_main",
    "is_known_cli_command",
    "lineage_main",
    "main",
    "promote_main",
    "rollback_main",
    "rollout_main",
    "train_main",
]
