from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence


class PiiType(str, Enum):
    EMAIL = 'email'
    PHONE = 'phone'
    PASSPORT = 'passport'
    CARD = 'card'
    ADDRESS = 'address'
    TAX_ID = 'tax_id'
    SECRET = 'secret'


@dataclass(frozen=True)
class PiiFinding:
    pii_type: PiiType
    value_excerpt: str
    start: int
    end: int
    confidence: float


@dataclass(frozen=True)
class PiiGuardResult:
    findings: tuple[PiiFinding, ...]
    contains_pii: bool
    risk_score: int

    def redact(self, text: str, replacement: str = '[REDACTED]') -> str:
        if not self.findings:
            return text

        segments: list[str] = []
        last = 0
        for finding in sorted(self.findings, key=lambda f: (f.start, f.end)):
            if finding.start < last:
                continue
            segments.append(text[last:finding.start])
            segments.append(replacement)
            last = finding.end
        segments.append(text[last:])
        return ''.join(segments)


class PIIGuard:
    DEFAULT_PATTERNS: Sequence[tuple[PiiType, re.Pattern[str], float]] = (
        (
            PiiType.EMAIL,
            re.compile(r'\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b', re.IGNORECASE),
            0.98,
        ),
        (
            PiiType.PHONE,
            re.compile(r'\b(?:\+?\d{1,3}[\s\-]?)?(?:\(?\d{2,4}\)?[\s\-]?){2,4}\d{2,4}\b'),
            0.82,
        ),
        (
            PiiType.CARD,
            re.compile(r'\b(?:\d[ -]*?){13,19}\b'),
            0.92,
        ),
        (
            PiiType.TAX_ID,
            re.compile(r'\b[A-Z0-9]{10,16}\b'),
            0.60,
        ),
        (
            PiiType.SECRET,
            re.compile(r'(?i)\b(?:api[_\-]?key|access[_\-]?token|refresh[_\-]?token|secret|private[_\-]?key)\b\s*[:=]\s*([^\s,;]+)'),
            0.96,
        ),
    )

    def __init__(self, patterns: Iterable[tuple[PiiType, re.Pattern[str], float]] | None = None) -> None:
        self._patterns = tuple(patterns or self.DEFAULT_PATTERNS)

    def inspect(self, text: str) -> PiiGuardResult:
        findings: list[PiiFinding] = []
        for pii_type, pattern, confidence in self._patterns:
            for match in pattern.finditer(text):
                value = match.group(0)
                if pii_type == PiiType.TAX_ID and not any(ch.isdigit() for ch in value):
                    continue
                findings.append(
                    PiiFinding(
                        pii_type=pii_type,
                        value_excerpt=self._mask_excerpt(value),
                        start=match.start(),
                        end=match.end(),
                        confidence=confidence,
                    )
                )

        findings = self._deduplicate(findings)
        risk_score = 0
        for finding in findings:
            if finding.pii_type in {PiiType.CARD, PiiType.PASSPORT, PiiType.TAX_ID, PiiType.SECRET}:
                risk_score += 5
            else:
                risk_score += 3

        return PiiGuardResult(findings=tuple(findings), contains_pii=bool(findings), risk_score=risk_score)

    @staticmethod
    def _mask_excerpt(value: str) -> str:
        if len(value) <= 4:
            return '*' * len(value)
        return value[:2] + ('*' * (len(value) - 4)) + value[-2:]

    @staticmethod
    def _deduplicate(findings: list[PiiFinding]) -> list[PiiFinding]:
        result: list[PiiFinding] = []
        seen: set[tuple[int, int, str]] = set()
        for item in sorted(findings, key=lambda x: (x.start, x.end, x.pii_type.value)):
            key = (item.start, item.end, item.pii_type.value)
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result
