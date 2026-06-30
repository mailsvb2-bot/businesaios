from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
from threading import RLock
from typing import Any

from governance.persistence_codec import atomic_write_json, read_json_or_default


CANON_MARKET_INTELLIGENCE_COMPLIANCE_STORE = True


def _text(value: object, *, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _store_path() -> Path:
    explicit = _text(os.getenv("BUSINESAIOS_MARKET_INTELLIGENCE_COMPLIANCE_STORE_PATH"))
    if explicit:
        return Path(explicit)
    data_dir = _text(os.getenv("DATA_DIR"), default=".runtime_data")
    return Path(data_dir) / "governance" / "market_intelligence_compliance_store.json"


@dataclass(frozen=True)
class ComplianceProviderPolicy:
    provider: str
    allow_access: bool = True
    risk_level: str = "standard"
    retention_days: int | None = None
    robots_aware_override: bool | None = None
    terms_aware_override: bool | None = None
    minimize_personal_data: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", _text(self.provider))
        object.__setattr__(self, "risk_level", _text(self.risk_level, default="standard"))
        object.__setattr__(self, "retention_days", int(self.retention_days) if self.retention_days is not None else None)

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "allow_access": bool(self.allow_access),
            "risk_level": self.risk_level,
            "retention_days": self.retention_days,
            "robots_aware_override": self.robots_aware_override,
            "terms_aware_override": self.terms_aware_override,
            "minimize_personal_data": bool(self.minimize_personal_data),
        }


class PersistentMarketIntelligenceComplianceStore:
    """Persistence only. No routing or hidden heuristics."""

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else _store_path()
        self._lock = RLock()
        self._state: dict[str, Any] = {"providers": {}, "policy_audit": [], "policy_version": 0}
        self._load()

    def get_provider_policy(self, provider: str) -> ComplianceProviderPolicy | None:
        raw = dict(self._state.get("providers", {})).get(_text(provider))
        if not isinstance(raw, dict):
            return None
        return ComplianceProviderPolicy(**raw)

    def upsert_provider_policy(self, policy: ComplianceProviderPolicy) -> ComplianceProviderPolicy:
        with self._lock:
            previous = dict(self._state.get("providers", {})).get(policy.provider)
            self._state.setdefault("providers", {})[policy.provider] = policy.as_dict()
            self._state["policy_version"] = int(self._state.get("policy_version", 0)) + 1
            self._state.setdefault("policy_audit", []).append({
                "version": int(self._state["policy_version"]),
                "provider": policy.provider,
                "previous": dict(previous) if isinstance(previous, dict) else None,
                "current": policy.as_dict(),
            })
            self._trim_audit()
            self._flush()
            return policy

    def policy_audit(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(item) for item in list(self._state.get("policy_audit", [])) if isinstance(item, dict))

    def snapshot(self) -> dict[str, Any]:
        return {
            "providers": {key: dict(value) for key, value in dict(self._state.get("providers", {})).items()},
            "policy_audit": list(self.policy_audit()),
            "policy_version": int(self._state.get("policy_version", 0)),
        }

    def _load(self) -> None:
        raw = read_json_or_default(self._path, default=self._state)
        if isinstance(raw, dict):
            self._state = {
                "providers": dict(raw.get("providers", {})),
                "policy_audit": list(raw.get("policy_audit", [])),
                "policy_version": int(raw.get("policy_version", 0)),
            }

    def _trim_audit(self) -> None:
        audit = list(self._state.get("policy_audit", []))
        if len(audit) > 1000:
            self._state["policy_audit"] = audit[-1000:]

    def _flush(self) -> None:
        atomic_write_json(self._path, self._state)


__all__ = [
    "CANON_MARKET_INTELLIGENCE_COMPLIANCE_STORE",
    "ComplianceProviderPolicy",
    "PersistentMarketIntelligenceComplianceStore",
]
