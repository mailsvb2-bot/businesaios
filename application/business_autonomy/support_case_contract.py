from __future__ import annotations

"""Canonical support-case input contract; persistence is owned by the future support-case store."""

import re
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class SupportCaseCategory(StrEnum):
    GENERAL = "general"
    BILLING = "billing"
    TECHNICAL = "technical"
    SECURITY = "security"
    INTEGRATION = "integration"


class SupportCaseStatus(StrEnum):
    OPEN = "open"
    CLAIMED = "claimed"
    RESOLVED = "resolved"


_CREDENTIAL_LABEL = (
    r"(?:api[_ -]?key|access[_ -]?token|secret|password|authorization|"
    r"api[ _-]?ключ|ключ[ _-]?api|токен[ _-]?доступа|секрет|пароль)"
)
_CREDENTIAL_PATTERNS = (
    re.compile(rf"(?i)\b{_CREDENTIAL_LABEL}\s*[:=]\s*\S{{8,}}"),
    re.compile(rf"(?i)\b{_CREDENTIAL_LABEL}\s+(?:is|equals?|это|равен|равно)\s+[\"'\x60]?[^\s\"'\x60]{{16,}}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~-]{16,}"),
    re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
)


def normalize_support_case_id(value: object) -> str:
    try:
        return str(UUID(str(value or "").strip()))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("support_case_id must be a valid UUID") from exc


def normalize_support_category(value: SupportCaseCategory | str) -> SupportCaseCategory:
    try:
        return value if isinstance(value, SupportCaseCategory) else SupportCaseCategory(str(value).strip())
    except ValueError as exc:
        raise ValueError("unsupported support case category") from exc


def normalize_support_summary(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("support case summary must be text")
    summary = re.sub(r"\s+", " ", value.replace("\x00", " ")).strip()
    if not 3 <= len(summary) <= 1000:
        raise ValueError("support case summary must be 3..1000 characters")
    if any(pattern.search(summary) for pattern in _CREDENTIAL_PATTERNS):
        raise ValueError("support case summary must not contain credentials or secrets")
    return summary


@dataclass(frozen=True, slots=True)
class SupportCase:
    id: str
    tenant_id: str
    business_id: str
    category: SupportCaseCategory
    summary: str
    status: SupportCaseStatus
    created_by_member_id: str
    claimed_by_operator_user_id: str | None
    created_at: str
    updated_at: str
    claimed_at: str | None
    resolved_at: str | None
