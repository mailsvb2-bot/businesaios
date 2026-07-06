"""Canonical command catalog for platform-support entrypoints."""

from __future__ import annotations

from runtime.platform.support.command_registry import is_known_command, known_command_set

CLI_COMMANDS = known_command_set((
    "audit",
    "checkpoints",
    "datasets",
    "evaluate",
    "experiments",
    "governance",
    "inspect",
    "lineage",
    "main",
    "promote",
    "rollback",
    "rollout",
    "train",
))

SCRIPT_COMMANDS = known_command_set((
    "audit_promotion_history",
    "backfill_rollouts",
    "cleanup_artifacts",
    "compact_replay",
    "generate_model_cards",
    "migrate_schemas",
    "rebuild_feature_stats",
    "rebuild_lineage",
    "recalculate_eval_scores",
    "verify_checkpoints",
))


def is_known_cli_command(command: str | None) -> bool:
    return is_known_command(command, commands=CLI_COMMANDS)


def is_known_script_command(command: str | None) -> bool:
    return is_known_command(command, commands=SCRIPT_COMMANDS)


__all__ = [
    "CLI_COMMANDS",
    "SCRIPT_COMMANDS",
    "is_known_cli_command",
    "is_known_script_command",
]
