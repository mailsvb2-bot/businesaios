"""Compat shim for application.governance.governance_service."""

from __future__ import annotations


# project_business_memory_governance_summary
from application.governance.governance_service import GovernanceService as _OwnerGovernanceService
from application.governance.governance_service import *  # noqa: F401,F403


class GovernanceService(_OwnerGovernanceService):
    pass
