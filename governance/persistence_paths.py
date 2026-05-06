from __future__ import annotations

import os
from pathlib import Path


CANON_GOVERNANCE_PERSISTENCE_PATHS = True


def governance_data_dir() -> Path:
    explicit = os.getenv("BUSINESAIOS_GOVERNANCE_DATA_DIR", "").strip()
    if explicit:
        return Path(explicit)
    data_dir = os.getenv("DATA_DIR", "data").strip() or "data"
    return Path(data_dir) / "governance"


def approval_store_path() -> Path:
    explicit = os.getenv("BUSINESAIOS_APPROVAL_STORE_PATH", "").strip()
    if explicit:
        return Path(explicit)
    return governance_data_dir() / "approvals.json"


def kill_switch_store_path() -> Path:
    explicit = os.getenv("BUSINESAIOS_KILL_SWITCH_STORE_PATH", "").strip()
    if explicit:
        return Path(explicit)
    return governance_data_dir() / "kill_switches.json"


def control_plane_audit_log_path() -> Path:
    explicit = os.getenv("BUSINESAIOS_CONTROL_PLANE_AUDIT_LOG_PATH", "").strip()
    if explicit:
        return Path(explicit)
    return governance_data_dir() / "control_plane_audit.jsonl"


def operator_override_store_path() -> Path:
    explicit = os.getenv("BUSINESAIOS_OPERATOR_OVERRIDE_STORE_PATH", "").strip()
    if explicit:
        return Path(explicit)
    return governance_data_dir() / "operator_overrides.json"


def tenant_policy_override_store_path() -> Path:
    explicit = os.getenv("BUSINESAIOS_TENANT_POLICY_OVERRIDE_STORE_PATH", "").strip()
    if explicit:
        return Path(explicit)
    return governance_data_dir() / "tenant_policy_overrides.json"


__all__ = [
    "CANON_GOVERNANCE_PERSISTENCE_PATHS",
    "approval_store_path",
    "governance_data_dir",
    "control_plane_audit_log_path",
    "operator_override_store_path",
    "kill_switch_store_path",
    "tenant_policy_override_store_path",
]
