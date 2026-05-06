from __future__ import annotations

from dataclasses import dataclass

from crm.onboarding.crm_oauth_contract import CrmOAuthStartRequest


@dataclass
class InMemoryCrmOAuthStateStore:
    _items: dict[str, CrmOAuthStartRequest]

    def __init__(self) -> None:
        self._items = {}

    def save(self, request: CrmOAuthStartRequest) -> None:
        self._items[request.state_token] = request

    def pop(self, state_token: str) -> CrmOAuthStartRequest:
        return self._items.pop(state_token)
