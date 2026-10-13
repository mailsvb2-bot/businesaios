"""Advisory funnel intelligence.

This package is deliberately non-authoritative. It derives evidence and
constraints for the canonical BusinessAIOS owners; it does not issue decisions,
create durable tasks, dispatch providers, own memory, or persist business state.
"""

from .advisory import (
    assess_followup_constraints,
    assess_inbound_evidence,
    assess_offer_evidence,
    derive_conversation_stage,
)
from .contracts import (
    CommercialEvidence,
    DerivedConversationStage,
    FollowupConstraintAssessment,
    FollowupConstraintContext,
    IngressAssessment,
    IngressClassification,
    ScopedInboundEvidence,
    VerifiedOfferEvidence,
)
from .signals import ConversationSignals, FatigueInputs, PressureInputs, fatigue_score, pressure_budget

__all__ = [
    "CommercialEvidence",
    "ConversationSignals",
    "DerivedConversationStage",
    "FatigueInputs",
    "FollowupConstraintAssessment",
    "FollowupConstraintContext",
    "IngressAssessment",
    "IngressClassification",
    "PressureInputs",
    "ScopedInboundEvidence",
    "VerifiedOfferEvidence",
    "assess_followup_constraints",
    "assess_inbound_evidence",
    "assess_offer_evidence",
    "derive_conversation_stage",
    "fatigue_score",
    "pressure_budget",
]
