from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Pattern


CANON_PII_REDACTION_POLICY = True


@dataclass(frozen=True)
class PIIRedactionPolicy:
    replacement: str = '<redacted>'
    email_pattern: Pattern[str] = field(
        default_factory=lambda: re.compile(r'([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})')
    )
    phone_pattern: Pattern[str] = field(
        default_factory=lambda: re.compile(r'(\+?\d[\d\s().-]{7,}\d)')
    )
    card_pattern: Pattern[str] = field(
        default_factory=lambda: re.compile(r'\b(?:\d[ -]*?){13,19}\b')
    )
    ipv4_pattern: Pattern[str] = field(
        default_factory=lambda: re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
    )
    ipv6_pattern: Pattern[str] = field(
        default_factory=lambda: re.compile(r'\b(?:[A-Fa-f0-9]{1,4}:){2,7}[A-Fa-f0-9]{1,4}\b')
    )
    iban_pattern: Pattern[str] = field(
        default_factory=lambda: re.compile(r'\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b')
    )

    def redact_text(self, value: str) -> str:
        text = str(value)
        for pattern in (
            self.email_pattern,
            self.phone_pattern,
            self.card_pattern,
            self.ipv4_pattern,
            self.ipv6_pattern,
            self.iban_pattern,
        ):
            text = pattern.sub(self.replacement, text)
        return text


__all__ = [
    'CANON_PII_REDACTION_POLICY',
    'PIIRedactionPolicy',
]
