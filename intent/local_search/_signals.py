from __future__ import annotations


def normalize_local_search_text(text: str) -> str:
    return str(text).lower()


def has_near_me_signal(text: str) -> bool:
    lowered = normalize_local_search_text(text)
    return "near me" in lowered or "рядом" in lowered


def build_local_service_query(text: str) -> dict[str, object]:
    lowered = normalize_local_search_text(text)
    return {"query": lowered, "tokens": tuple(lowered.split())}


def classify_local_intent(text: str) -> str:
    return "local" if has_near_me_signal(text) else "any"


def build_geo_radius(text: str) -> int:
    return 5 if has_near_me_signal(text) else 25


def build_service_area_match_prep(text: str) -> dict[str, object]:
    lowered = normalize_local_search_text(text)
    return {"service_area_ready": True, "text": lowered}
