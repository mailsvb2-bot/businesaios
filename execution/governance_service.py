"""Compat shim for application.governance.governance_service."""

from __future__ import annotations


# project_business_memory_governance_summary
from application.governance.governance_service import GovernanceService as _OwnerGovernanceService
from application.governance.governance_service import *  # noqa: F401,F403
from execution.headless_paths import build_headless_runtime_paths  # arch-lock visible shared owner


class GovernanceService(_OwnerGovernanceService):
    pass
