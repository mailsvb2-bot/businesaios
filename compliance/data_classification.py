from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional, Protocol, Sequence


class DataCategory(str, Enum):
    PUBLIC = 'public'
    INTERNAL = 'internal'
    CONFIDENTIAL = 'confidential'
    RESTRICTED = 'restricted'
    REGULATED = 'regulated'


class DataSensitivity(str, Enum):
    LOW = 'low'
    MODERATE = 'moderate'
    HIGH = 'high'
    CRITICAL = 'critical'


@dataclass(frozen=True)
class DataAsset:
    asset_id: str
    name: str
    content_type: str
    tags: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)
    source_system: Optional[str] = None
    region_hint: Optional[str] = None


@dataclass(frozen=True)
class DataClassificationResult:
    category: DataCategory
    sensitivity: DataSensitivity
    pii_present: bool
    secret_present: bool
    regulated_markers: tuple[str, ...]
    retention_profile: str
    reasons: tuple[str, ...]
    classification_confidence: float


class DataClassifier(Protocol):
    def classify(self, asset: DataAsset) -> DataClassificationResult: ...


class KeywordDataClassifier:
    """Deterministic rule-based classifier. Must remain explainable."""

    def __init__(
        self,
        regulated_keywords: Optional[Mapping[str, Sequence[str]]] = None,
        pii_keywords: Optional[Sequence[str]] = None,
        secret_keywords: Optional[Sequence[str]] = None,
    ) -> None:
        self._regulated_keywords = {
            key.lower(): tuple(v.lower() for v in values)
            for key, values in (
                regulated_keywords
                or {
                    'gdpr': ('gdpr', 'personal_data', 'eu_personal'),
                    'finance': ('iban', 'payment', 'invoice', 'cardholder'),
                    'health': ('medical', 'diagnosis', 'patient'),
                    'identity': ('passport', 'kyc', 'identity_document'),
                }
            ).items()
        }
        self._pii_keywords = tuple(
            x.lower() for x in (pii_keywords or ('email', 'phone', 'address', 'passport', 'birthdate', 'tax_id'))
        )
        self._secret_keywords = tuple(
            x.lower() for x in (secret_keywords or ('token', 'secret', 'credential', 'private_key', 'api_key'))
        )

    def classify(self, asset: DataAsset) -> DataClassificationResult:
        haystack = ' '.join(
            [
                asset.name,
                asset.content_type,
                ' '.join(asset.tags),
                ' '.join(f'{k}:{v}' for k, v in asset.metadata.items()),
                asset.source_system or '',
                asset.region_hint or '',
            ]
        ).lower()

        reasons: list[str] = []
        regulated_markers: list[str] = []

        pii_present = any(marker in haystack for marker in self._pii_keywords)
        secret_present = any(marker in haystack for marker in self._secret_keywords)

        if pii_present:
            reasons.append('PII markers detected')
        if secret_present:
            reasons.append('Secret-like markers detected')

        for profile, markers in self._regulated_keywords.items():
            if any(marker in haystack for marker in markers):
                regulated_markers.append(profile)
                reasons.append(f'Regulated marker detected: {profile}')

        if regulated_markers and (pii_present or secret_present):
            category = DataCategory.REGULATED
            sensitivity = DataSensitivity.CRITICAL
            retention_profile = 'regulated_pii' if pii_present else 'regulated'
            confidence = 0.95
        elif regulated_markers:
            category = DataCategory.RESTRICTED
            sensitivity = DataSensitivity.HIGH
            retention_profile = 'regulated'
            confidence = 0.90
        elif secret_present:
            category = DataCategory.RESTRICTED
            sensitivity = DataSensitivity.CRITICAL
            retention_profile = 'secrets'
            confidence = 0.92
        elif pii_present:
            category = DataCategory.CONFIDENTIAL
            sensitivity = DataSensitivity.HIGH
            retention_profile = 'personal_data'
            confidence = 0.88
        elif 'internal' in haystack or 'private' in haystack:
            category = DataCategory.INTERNAL
            sensitivity = DataSensitivity.MODERATE
            retention_profile = 'internal_default'
            reasons.append('Internal marker detected')
            confidence = 0.75
        else:
            category = DataCategory.PUBLIC
            sensitivity = DataSensitivity.LOW
            retention_profile = 'public_default'
            reasons.append('No restricted markers detected')
            confidence = 0.70

        return DataClassificationResult(
            category=category,
            sensitivity=sensitivity,
            pii_present=pii_present,
            secret_present=secret_present,
            regulated_markers=tuple(sorted(set(regulated_markers))),
            retention_profile=retention_profile,
            reasons=tuple(reasons),
            classification_confidence=max(0.0, min(1.0, confidence)),
        )
