from __future__ import annotations

from collections.abc import Container

from ..errors import UnauthorizedOverrideError


class UnauthorizedOverrideGuard:
    def ensure_allowed(self, actor_id: str, allowed_actor_ids: Container[str]) -> None:
        if actor_id not in allowed_actor_ids:
            raise UnauthorizedOverrideError(
                f"actor '{actor_id}' is not allowed to override"
            )
