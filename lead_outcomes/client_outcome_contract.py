from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Mapping

CANON_CLIENT_OUTCOME_CONTRACT = True


def _text(value: object) -> str:
    return str(value or '').strip()


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


@dataclass(frozen=True, slots=True)
class ClientOutcomePackage:
    package_id: str
    label: str
    requested_clients: int
    price_per_verified_client: float
    currency: str = 'EUR'
    attribution_window_days: int = 30
    new_client_window_days: int = 180
    allow_returning_clients: bool = False
    require_payment_proof: bool = False
    require_crm_proof: bool = True
    trust_tier: str = 'tier0_manual'

    def normalized_copy(self) -> 'ClientOutcomePackage':
        requested = max(1, int(self.requested_clients))
        return ClientOutcomePackage(
            package_id=_text(self.package_id),
            label=_text(self.label) or f'{requested} clients',
            requested_clients=requested,
            price_per_verified_client=max(0.0, float(self.price_per_verified_client)),
            currency=_text(self.currency).upper() or 'EUR',
            attribution_window_days=max(1, int(self.attribution_window_days)),
            new_client_window_days=max(1, int(self.new_client_window_days)),
            allow_returning_clients=bool(self.allow_returning_clients),
            require_payment_proof=bool(self.require_payment_proof),
            require_crm_proof=bool(self.require_crm_proof),
            trust_tier=_text(self.trust_tier) or 'tier0_manual',
        )


@dataclass(frozen=True, slots=True)
class ClientOutcomeOrder:
    order_id: str
    business_id: str
    tenant_id: str
    package: ClientOutcomePackage
    created_at: datetime
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def expires_at(self) -> datetime:
        return self.created_at + timedelta(days=self.package.attribution_window_days)


@dataclass(frozen=True, slots=True)
class OutcomeLead:
    lead_id: str
    order_id: str
    business_id: str
    tenant_id: str
    captured_at: datetime
    tracking_token: str
    source_channel: str
    session_id: str = ''
    click_id: str = ''
    phone_hash: str = ''
    email_hash: str = ''
    external_customer_id: str = ''
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def identity_fingerprint(self) -> str:
        parts = [
            _text(self.phone_hash).casefold(),
            _text(self.email_hash).casefold(),
            _text(self.external_customer_id).casefold(),
        ]
        return '|'.join(part for part in parts if part)


@dataclass(frozen=True, slots=True)
class ClientProofEvent:
    proof_id: str
    lead_id: str
    business_id: str
    tenant_id: str
    occurred_at: datetime
    proof_type: str
    status: str
    source: str
    external_ref: str = ''
    amount: float = 0.0
    currency: str = 'EUR'
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def is_positive(self) -> bool:
        normalized_status = _text(self.status).casefold()
        return normalized_status in {'verified', 'confirmed', 'paid', 'won', 'completed', 'succeeded'}


@dataclass(frozen=True, slots=True)
class AttributionVerdict:
    lead_id: str
    attributed: bool
    reason_code: str
    source_of_truth: str
    confidence: float
    external_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FraudVerdict:
    lead_id: str
    allowed: bool
    fraud_score: float
    reason_code: str
    triggered_signals: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EligibilityVerdict:
    lead_id: str
    eligible: bool
    reason_code: str
    category: str


@dataclass(frozen=True, slots=True)
class VerifiedClientVerdict:
    lead_id: str
    verified: bool
    billable: bool
    reason_code: str
    confidence: float
    attribution: AttributionVerdict
    fraud: FraudVerdict
    eligibility: EligibilityVerdict
    proof_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BillableClientRecord:
    record_id: str
    tenant_id: str
    business_id: str
    order_id: str
    lead_id: str
    package_id: str
    verified_at: datetime
    unit_price: float
    currency: str
    quantity: int = 1
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def amount(self) -> float:
        return round(float(self.unit_price) * int(self.quantity), 2)

    def normalized_metadata(self) -> dict[str, Any]:
        return _safe_dict(self.metadata)
