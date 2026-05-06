from dataclasses import dataclass

from routing.demand_router import DemandRouter


@dataclass(frozen=True)
class _Req:
    request_id: str = "r1"


@dataclass(frozen=True)
class _Intent:
    pass


@dataclass(frozen=True)
class _Candidate:
    business_id: str
    score: float
    blocked: bool = False


@dataclass(frozen=True)
class _Bundle:
    candidates: tuple
    audit: dict


class _StateBuilder:
    def build(self, business_id: str):
        raise AssertionError("should not be called when profile lookup fails")


class _Directory:
    pass


def test_router_skips_candidates_when_directory_has_no_profile_accessors() -> None:
    router = DemandRouter(business_directory=_Directory(), business_live_state_builder=_StateBuilder())
    prepared = router.prepare(
        request=_Req(),
        intent=_Intent(),
        match_bundle=_Bundle(candidates=(_Candidate("biz-1", 0.9),), audit={}),
    )
    assert prepared["requires_manual_review"] is True
    assert prepared["ranked_candidates"] == ()
