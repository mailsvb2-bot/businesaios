from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


CANON_AUTONOMY_KILL_SWITCH = True


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _text(value: object) -> str:
    return str(value or "").strip()


@dataclass(frozen=True)
class KillSwitchRule:
    tenant_id: str = "*"
    business_id: str = "*"
    integration_domain: str = "*"
    action_type: str = "*"
    active: bool = True
    reason: str = ""

    def matches(self, *, tenant_id: str, business_id: str, integration_domain: str, action_type: str) -> bool:
        def _match(rule_value: str, actual: str) -> bool:
            return rule_value == "*" or rule_value == actual
        return bool(self.active) and _match(self.tenant_id, tenant_id) and _match(self.business_id, business_id) and _match(self.integration_domain, integration_domain) and _match(self.action_type, action_type)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "business_id": self.business_id,
            "integration_domain": self.integration_domain,
            "action_type": self.action_type,
            "active": bool(self.active),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class KillSwitchDecision:
    active: bool
    reason: str
    matched_rules: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {"active": bool(self.active), "reason": str(self.reason), "matched_rules": [dict(item) for item in self.matched_rules]}


class FileAutonomyKillSwitchRegistry:
    def __init__(self, *, root_dir: Path) -> None:
        self._root_dir = Path(root_dir)
        self._root_dir.mkdir(parents=True, exist_ok=True)
        self._path = self._root_dir / "kill_switch_rules.json"

    def _load(self) -> list[KillSwitchRule]:
        if not self._path.exists():
            return []
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return []
        rows = data if isinstance(data, list) else []
        result: list[KillSwitchRule] = []
        for row in rows:
            item = _safe_dict(row)
            result.append(KillSwitchRule(
                tenant_id=_text(item.get("tenant_id") or "*") or "*",
                business_id=_text(item.get("business_id") or "*") or "*",
                integration_domain=_text(item.get("integration_domain") or "*") or "*",
                action_type=_text(item.get("action_type") or "*") or "*",
                active=bool(item.get("active", True)),
                reason=_text(item.get("reason")),
            ))
        return result

    def replace_rules(self, rules: list[KillSwitchRule]) -> None:
        payload = [rule.to_dict() for rule in rules]
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def evaluate(self, *, tenant_id: str, business_id: str, integration_domain: str, action_type: str) -> KillSwitchDecision:
        matched = [rule.to_dict() for rule in self._load() if rule.matches(tenant_id=tenant_id, business_id=business_id, integration_domain=integration_domain, action_type=action_type)]
        if matched:
            return KillSwitchDecision(active=True, reason=str(matched[0].get("reason") or "autonomy_kill_switch_active"), matched_rules=tuple(matched))
        return KillSwitchDecision(active=False, reason="kill_switch_clear")


__all__ = [
    "CANON_AUTONOMY_KILL_SWITCH",
    "FileAutonomyKillSwitchRegistry",
    "KillSwitchDecision",
    "KillSwitchRule",
]
