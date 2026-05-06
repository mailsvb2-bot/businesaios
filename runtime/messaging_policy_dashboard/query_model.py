from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MessagingPolicyDashboardQuery:
    tenant_id: str
    user_id: str = ""
    date_from: str = ""
    date_to: str = ""
    limit: int = 500
