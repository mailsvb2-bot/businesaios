from __future__ import annotations

"""User role segmentation (product UX).

Roles:
  - owner: business owner / primary decision maker
  - marketer: marketing operator / agency
  - operator: internal operator / assistant

Role is derived from user settings (transport-agnostic).
This is intentionally dumb and explicit.
"""

from dataclasses import dataclass
from typing import Mapping, Any, Literal

UserRole = Literal["owner", "marketer", "operator"]


@dataclass(frozen=True)
class UserRoleInfo:
    role: UserRole

    @staticmethod
    def from_settings(settings: Mapping[str, Any] | None) -> "UserRoleInfo":
        if not isinstance(settings, Mapping):
            return UserRoleInfo("owner")
        raw = str(settings.get("user:role") or "").strip().lower()
        if raw in {"owner", "marketer", "operator"}:
            return UserRoleInfo(raw)  # type: ignore[arg-type]
        return UserRoleInfo("owner")
