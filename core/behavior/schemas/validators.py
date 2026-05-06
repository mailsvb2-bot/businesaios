from __future__ import annotations

from core.behavior.contracts.market_field import MarketField
from core.behavior.contracts.micro_spinor import MicroSpinor
from core.behavior.contracts.org_field import OrgField
from core.behavior.contracts.person_field import PersonField
from core.behavior.contracts.segment_field import SegmentField


def validate_micro_spinor(spinor: MicroSpinor) -> None:
    if len(spinor.psi_re) != 4 or len(spinor.psi_im) != 4:
        raise ValueError("MicroSpinor must contain 4 complex components")
    if spinor.started_at > spinor.ended_at:
        raise ValueError("MicroSpinor started_at cannot be after ended_at")


def validate_person_field(field: PersonField) -> None:
    for spinor in field.micro_spinors:
        validate_micro_spinor(spinor)


def validate_org_field(field: OrgField) -> None:
    for role_field in field.role_fields.values():
        validate_person_field(role_field)


def validate_segment_field(field: SegmentField) -> None:
    for person_field in field.person_fields:
        validate_person_field(person_field)


def validate_market_field(field: MarketField) -> None:
    for segment_field in field.segment_fields:
        validate_segment_field(segment_field)
