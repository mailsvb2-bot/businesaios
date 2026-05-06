from __future__ import annotations

from typing import Any, Protocol


class TransportPort(Protocol):
    def send(self, path: str, payload: dict[str, Any]) -> Any:
        ...


class Client:
    def __init__(self, transport: TransportPort) -> None:
        self._transport = transport

    def request(self, path: str, payload: dict[str, Any]) -> Any:
        return self._transport.send(path, payload)

__all__ = [
    "Client",
    "TransportPort",
]
