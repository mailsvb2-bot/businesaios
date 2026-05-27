from __future__ import annotations

from pathlib import Path
from typing import Any

from core.behavior.operator_policy_catalogs.model import (
    OperatorPolicyCatalog as CompatOperatorPolicyCatalog,
)
from core.behavior.operator_policy_catalogs.model import (
    OperatorPolicyRule as CompatOperatorPolicyRule,
)
from core.behavior.operator_policy_catalogs.models import OperatorPolicyCatalog
from core.behavior.operator_policy_catalogs.parser import parse_operator_policy_catalog

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


class OperatorPolicyCatalogLoader:
    def __init__(self, root: Path) -> None:
        self._root = root

    def load(self, catalog_ref: str) -> OperatorPolicyCatalog | None:
        if yaml is None:
            return None
        path = self._root / f"{catalog_ref}.yaml"
        if not path.exists():
            return None
        payload: Any = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            return None
        return parse_operator_policy_catalog(payload)


def _parse_compat_rule(data: dict[str, Any] | None) -> CompatOperatorPolicyRule:
    if not isinstance(data, dict):
        return CompatOperatorPolicyRule()
    allow = set(data.get("allow") or data.get("allowed") or [])
    deny = set(data.get("deny") or data.get("denied") or [])
    return CompatOperatorPolicyRule(allow=allow, deny=deny)


def load_operator_policy_catalog(
    path: str | Path,
    *,
    name: str | None = None,
) -> CompatOperatorPolicyCatalog:
    """Compatibility loader for legacy policy resolver surface."""
    if yaml is None:
        return CompatOperatorPolicyCatalog(name=name or "default", version=1)
    p = Path(path)
    payload = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        payload = {}
    catalog_name = str(name or payload.get("name") or p.stem)
    version = int(payload.get("version", 1))

    defaults = _parse_compat_rule(payload.get("defaults"))
    stages = {
        str(k): _parse_compat_rule(v if isinstance(v, dict) else None)
        for k, v in (payload.get("stages") or {}).items()
    }
    roles = {
        str(k): _parse_compat_rule(v if isinstance(v, dict) else None)
        for k, v in (payload.get("roles") or {}).items()
    }
    stage_role: dict[str, dict[str, CompatOperatorPolicyRule]] = {}
    for stage, mapping in (payload.get("stage_role") or {}).items():
        if not isinstance(mapping, dict):
            continue
        stage_role[str(stage)] = {
            str(role): _parse_compat_rule(rule if isinstance(rule, dict) else None)
            for role, rule in mapping.items()
        }

    return CompatOperatorPolicyCatalog(
        name=catalog_name,
        version=version,
        defaults=defaults,
        stages=stages,
        roles=roles,
        stage_role=stage_role,
    )
