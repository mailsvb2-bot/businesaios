from __future__ import annotations

from threading import Lock

from interfaces.web.chat_widget.session_contract import WebChatSession


class InMemoryWebChatSessionStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._items: dict[str, WebChatSession] = {}

    def put(self, session: WebChatSession) -> None:
        with self._lock:
            self._items[str(session.session_id)] = session

    def get(self, session_id: str) -> WebChatSession | None:
        with self._lock:
            return self._items.get(str(session_id))
