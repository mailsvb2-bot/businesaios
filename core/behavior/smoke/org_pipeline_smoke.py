from __future__ import annotations

from pathlib import Path

from core.behavior.builders.behavioral_state_builder import build_org_behavioral_state


def run_org_pipeline_smoke(tmp_root: Path) -> dict[str, object]:
    catalog_root = tmp_root / "catalogs"
    policy_root = tmp_root / "policies"
    catalog_root.mkdir(parents=True, exist_ok=True)
    policy_root.mkdir(parents=True, exist_ok=True)
    return build_org_behavioral_state(
        "org-1",
        {
            "champion": [
                {"event_id": "1", "event_type": "message_open", "actor_role": "champion", "product": "demo"},
                {"event_id": "2", "event_type": "content_engage", "actor_role": "champion", "product": "demo"},
            ],
            "finance": [
                {"event_id": "3", "event_type": "price_view", "actor_role": "finance", "product": "demo"},
            ],
        },
        catalog_root=catalog_root,
        policy_root=policy_root,
    )
