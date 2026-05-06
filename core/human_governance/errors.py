from __future__ import annotations


class HumanGovernanceError(Exception):
    pass


class ReviewNotFoundError(HumanGovernanceError):
    pass


class ReviewAlreadyClosedError(HumanGovernanceError):
    pass


class UnauthorizedOverrideError(HumanGovernanceError):
    pass


class StaleReviewError(HumanGovernanceError):
    pass


class InvalidActorError(HumanGovernanceError):
    pass


class InvalidReasonError(HumanGovernanceError):
    pass


class InvalidReviewStateError(HumanGovernanceError):
    pass


class DuplicateOverrideError(HumanGovernanceError):
    pass
