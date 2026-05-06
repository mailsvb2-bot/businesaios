from __future__ import annotations

from pathlib import Path

from core.behavior.builders.behavioral_state_builder import build_behavioral_state


def run_person_pipeline_smoke(tmp_root: Path) -> dict[str, object]:
    catalog_root = tmp_root / "catalogs"
    policy_root = tmp_root / "policies"
    catalog_root.mkdir(parents=True, exist_ok=True)
    policy_root.mkdir(parents=True, exist_ok=True)
    return build_behavioral_state(
        "user-1",
        [
            {"event_id": "1", "event_type": "message_open", "channel": "telegram", "product": "demo"},
            {"event_id": "2", "event_type": "content_engage", "channel": "telegram", "product": "demo"},
        ],
        catalog_root=catalog_root,
        policy_root=policy_root,
    )
