from __future__ import annotations

_ALLOWED = {
    'pending': {'oauth_started', 'failed'},
    'oauth_started': {'authorized', 'failed'},
    'authorized': {'verified', 'failed'},
    'verified': {'active'},
    'active': set(),
    'failed': set(),
}


class CrmConnectionStateMachine:
    def transition(self, current: str, new: str) -> str:
        if new not in _ALLOWED.get(current, set()):
            raise ValueError(f'Invalid CRM connection transition: {current} -> {new}')
        return new
