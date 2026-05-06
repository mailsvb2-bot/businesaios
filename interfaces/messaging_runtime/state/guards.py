from __future__ import annotations


class InboundDuplicateDetected(RuntimeError):
    pass


class InboundIdempotencyGuard:
    def __init__(self, *, inbox_state_store, lock_store) -> None:
        self._inbox_state_store = inbox_state_store
        self._lock_store = lock_store

    def enter(self, message_id: str) -> None:
        key = self._key(message_id)
        if not self._lock_store.acquire(key):
            raise InboundDuplicateDetected(f"inbound lock already acquired: {message_id}")
        if self._inbox_state_store.has_seen(message_id):
            self._lock_store.release(key)
            raise InboundDuplicateDetected(f"inbound message already seen: {message_id}")

    def commit(self, message_id: str) -> None:
        key = self._key(message_id)
        try:
            self._inbox_state_store.mark_seen(message_id)
        finally:
            self._lock_store.release(key)

    def abort(self, message_id: str) -> None:
        self._lock_store.release(self._key(message_id))

    @staticmethod
    def _key(message_id: str) -> str:
        normalized = str(message_id or '').strip()
        if not normalized:
            raise ValueError('message_id is required')
        return f"inbound:{normalized}"
