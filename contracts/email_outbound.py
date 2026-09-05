from __future__ import annotations

import re
from dataclasses import dataclass
from email.utils import parseaddr

CANON_EMAIL_OUTBOUND_CONTRACT = True
_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_HOST_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?")
_ALLOWED_SECURITY = frozenset({"ssl", "starttls"})


def normalize_email_address(value: object) -> str:
    raw = str(value or "").strip()
    if any(char in raw for char in ("\r", "\n", "\x00")):
        raise ValueError("email address contains control characters")
    _display, address = parseaddr(raw)
    normalized = address.casefold().strip()
    if not normalized or len(normalized) > 320 or not _EMAIL_RE.fullmatch(normalized):
        raise ValueError("email address is invalid")
    if any(ord(char) < 32 or ord(char) == 127 for char in normalized):
        raise ValueError("email address contains control characters")
    return normalized


def normalize_smtp_host(value: object) -> str:
    host = str(value or "").strip().lower()
    if not host or len(host) > 253 or not _HOST_RE.fullmatch(host) or ".." in host:
        raise ValueError("SMTP host is invalid")
    return host


def normalize_smtp_port(value: object) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("SMTP port is invalid") from exc
    if port < 1 or port > 65535:
        raise ValueError("SMTP port is invalid")
    return port


def normalize_smtp_security(value: object) -> str:
    security = str(value or "").strip().lower()
    if security not in _ALLOWED_SECURITY:
        raise ValueError("SMTP security must be ssl or starttls")
    return security


@dataclass(frozen=True)
class EmailOutboundPayloadV1:
    recipient: str
    subject: str
    body: str

    def __post_init__(self) -> None:
        recipient = normalize_email_address(self.recipient)
        subject = " ".join(str(self.subject or "").replace("\x00", " ").split())
        body = str(self.body or "").replace("\x00", "").strip()
        if not subject or len(subject) > 240 or "\r" in subject or "\n" in subject:
            raise ValueError("email subject must be 1..240 safe characters")
        if not body or len(body) > 100_000:
            raise ValueError("email body must be 1..100000 characters")
        object.__setattr__(self, "recipient", recipient)
        object.__setattr__(self, "subject", subject)
        object.__setattr__(self, "body", body)


__all__ = [
    "CANON_EMAIL_OUTBOUND_CONTRACT",
    "EmailOutboundPayloadV1",
    "normalize_email_address",
    "normalize_smtp_host",
    "normalize_smtp_port",
    "normalize_smtp_security",
]
