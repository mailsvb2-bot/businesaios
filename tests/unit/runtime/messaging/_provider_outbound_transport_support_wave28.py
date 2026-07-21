from __future__ import annotations

from email.message import EmailMessage
from typing import Any

from runtime.messaging.outbound_message import OutboundMessage
from runtime.messaging.provider_config import ProviderConfig


def _cfg(
    *,
    mode: str = "webhook",
    endpoint: str = "https://provider.example/send",
    sender_value: str = "sender@example.com",
) -> ProviderConfig:
    return ProviderConfig(
        provider="demo",
        env_prefix="DEMO",
        mode=mode,
        endpoint=endpoint,
        sender=sender_value,
        token_present=True,
    )


def _msg(**overrides: Any) -> OutboundMessage:
    values: dict[str, Any] = {
        "decision_id": "decision-1",
        "correlation_id": "corr-1",
        "tenant_id": "tenant-1",
        "user_id": "recipient@example.com",
        "channel": "email",
        "text": "hello",
        "reply_markup": {"button": "ok"},
        "payload": {"subject": "Subject"},
    }
    values.update(overrides)
    return OutboundMessage(**values)


class _Headers:
    def __init__(self, values: dict[str, str] | None = None, *, fail: bool = False) -> None:
        self.values = dict(values or {})
        self.fail = fail

    def get(self, key: str) -> str | None:
        if self.fail:
            raise RuntimeError("headers unavailable")
        return self.values.get(key)


class _Response:
    def __init__(
        self,
        *,
        body: bytes,
        status: int | None = 200,
        code: int = 200,
        headers: Any = None,
    ) -> None:
        self._body = body
        self.status = status
        self._code = code
        self.headers = headers
        self.read_limit: int | None = None

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def getcode(self) -> int:
        return self._code

    def read(self, limit: int) -> bytes:
        self.read_limit = limit
        return self._body


class _SMTP:
    instances: list[_SMTP] = []

    def __init__(
        self,
        host: str,
        port: int,
        *,
        timeout: float,
        refused: dict[str, object] | None = None,
        fail_quit: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.refused = dict(refused or {})
        self.fail_quit = fail_quit
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.message: EmailMessage | None = None
        self.__class__.instances.append(self)

    def ehlo(self) -> None:
        self.calls.append(("ehlo", ()))

    def starttls(self) -> None:
        self.calls.append(("starttls", ()))

    def login(self, username: str, password: str) -> None:
        self.calls.append(("login", (username, password)))

    def send_message(self, message: EmailMessage) -> dict[str, object]:
        self.calls.append(("send_message", (message,)))
        self.message = message
        return self.refused

    def quit(self) -> None:
        self.calls.append(("quit", ()))
        if self.fail_quit:
            raise RuntimeError("quit failed")
