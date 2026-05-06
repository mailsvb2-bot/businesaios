from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..enums import GuardSeverity
from ..guard import GuardTrigger


@dataclass
class AdvisoryBoundaryGuard:
    forbidden_key_fragments: tuple[str, ...] = (
        "action",
        "execute",
        "launch",
        "apply",
        "dispatch",
        "send",
        "start_campaign",
        "campaign_id",
        "decision_id",
        "route",
    )

    def check(self, policy_advice: dict[str, Any]) -> GuardTrigger | None:
        bad_keys = sorted(self._find_forbidden_keys(policy_advice))
        if bad_keys:
            return GuardTrigger(
                code="advisory_boundary_violation",
                severity=GuardSeverity.BLOCK,
                message="Economics policy advice contains action-like fields and risks becoming a second brain.",
                details={"forbidden_keys": bad_keys},
            )
        return None

    def _find_forbidden_keys(self, value: Any, path: str = "") -> set[str]:
        found: set[str] = set()
        if isinstance(value, dict):
            for key, nested in value.items():
                key_str = str(key)
                full_path = f"{path}.{key_str}" if path else key_str
                lowered = key_str.lower()
                if any(fragment in lowered for fragment in self.forbidden_key_fragments):
                    found.add(full_path)
                found.update(self._find_forbidden_keys(nested, full_path))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                found.update(self._find_forbidden_keys(item, f"{path}[{index}]"))
        return found
