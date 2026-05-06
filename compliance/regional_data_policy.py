from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Optional, Sequence

from compliance.base import ComplianceControl, PolicyMetadata


class DataRegion(str, Enum):
    EU = 'eu'
    US = 'us'
    UK = 'uk'
    APAC = 'apac'
    GLOBAL = 'global'
    UNKNOWN = 'unknown'


@dataclass(frozen=True)
class RegionalPolicyDecision:
    allowed: bool
    source_region: DataRegion
    target_region: DataRegion
    cross_border: bool
    required_controls: tuple[ComplianceControl, ...]
    reason: str
    policy: PolicyMetadata


class RegionalDataPolicy:
    def __init__(
        self,
        allowed_transfers: Optional[Mapping[DataRegion, Sequence[DataRegion]]] = None,
        *,
        policy_version: str = '2.0',
    ) -> None:
        self._policy = PolicyMetadata(
            policy_name='regional_data_policy',
            policy_version=policy_version,
            tags=('region', 'residency'),
        )
        self._allowed_transfers = {
            DataRegion.EU: (DataRegion.EU, DataRegion.UK),
            DataRegion.UK: (DataRegion.UK, DataRegion.EU),
            DataRegion.US: (DataRegion.US,),
            DataRegion.APAC: (DataRegion.APAC,),
            DataRegion.GLOBAL: (DataRegion.GLOBAL,),
            DataRegion.UNKNOWN: (),
        }
        if allowed_transfers:
            self._allowed_transfers.update({k: tuple(v) for k, v in allowed_transfers.items()})

    def evaluate(
        self,
        *,
        source_region: str | DataRegion | None,
        target_region: str | DataRegion | None,
        contains_pii: bool,
        regulated: bool = False,
    ) -> RegionalPolicyDecision:
        src = self._normalize_region(source_region)
        dst = self._normalize_region(target_region)
        cross_border = src != dst

        if src == DataRegion.UNKNOWN or dst == DataRegion.UNKNOWN:
            return RegionalPolicyDecision(
                allowed=False,
                source_region=src,
                target_region=dst,
                cross_border=cross_border,
                required_controls=(),
                reason='Unknown region is fail-closed for compliance-sensitive transfers.',
                policy=self._policy,
            )
        if dst not in self._allowed_transfers.get(src, ()):
            return RegionalPolicyDecision(
                allowed=False,
                source_region=src,
                target_region=dst,
                cross_border=cross_border,
                required_controls=(),
                reason='Transfer denied by regional policy matrix.',
                policy=self._policy,
            )

        controls: list[ComplianceControl] = []
        if cross_border:
            controls.extend([ComplianceControl.TRANSFER_AUDIT, ComplianceControl.JURISDICTION_BASIS])
        if contains_pii:
            controls.append(ComplianceControl.PII_MINIMIZATION)
        if regulated:
            controls.append(ComplianceControl.LEGAL_BASIS_REVIEW)

        return RegionalPolicyDecision(
            allowed=True,
            source_region=src,
            target_region=dst,
            cross_border=cross_border,
            required_controls=tuple(sorted(set(controls), key=lambda x: x.value)),
            reason='Transfer allowed by regional policy.',
            policy=self._policy,
        )

    @staticmethod
    def _normalize_region(value: str | DataRegion | None) -> DataRegion:
        if isinstance(value, DataRegion):
            return value
        if value is None:
            return DataRegion.UNKNOWN
        normalized = str(value).strip().lower()
        for item in DataRegion:
            if item.value == normalized:
                return item
        return DataRegion.UNKNOWN
