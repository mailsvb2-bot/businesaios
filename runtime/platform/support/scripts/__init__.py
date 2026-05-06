from __future__ import annotations

from runtime.platform.support.scripts._main_stub import script_main

CANON_RUNTIME_SUPPORT_SCRIPTS_PACKAGE_OWNER = True
CANON_COMPAT_SHIM = True

SCRIPT_COMMANDS = (
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
)

def is_known_script_command(name: str) -> bool:
    return str(name).strip() in set(SCRIPT_COMMANDS)

def audit_promotion_history_main() -> int:
    return script_main("audit_promotion_history")

def backfill_rollouts_main() -> int:
    return script_main("backfill_rollouts")

def cleanup_artifacts_main() -> int:
    return script_main("cleanup_artifacts")

def compact_replay_main() -> int:
    return script_main("compact_replay")

def generate_model_cards_main() -> int:
    return script_main("generate_model_cards")

def migrate_schemas_main() -> int:
    return script_main("migrate_schemas")

def rebuild_feature_stats_main() -> int:
    return script_main("rebuild_feature_stats")

def rebuild_lineage_main() -> int:
    return script_main("rebuild_lineage")

def recalculate_eval_scores_main() -> int:
    return script_main("recalculate_eval_scores")

def verify_checkpoints_main() -> int:
    return script_main("verify_checkpoints")

__all__ = [
    "SCRIPT_COMMANDS",
    "is_known_script_command",
    "audit_promotion_history_main",
    "backfill_rollouts_main",
    "cleanup_artifacts_main",
    "compact_replay_main",
    "generate_model_cards_main",
    "migrate_schemas_main",
    "rebuild_feature_stats_main",
    "rebuild_lineage_main",
    "recalculate_eval_scores_main",
    "verify_checkpoints_main",
]
