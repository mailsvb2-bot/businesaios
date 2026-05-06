from __future__ import annotations

_BAND_ORDER = {"low": 0, "standard": 1, "premium": 2}


def constrain_price_band(candidate_band: str, max_band: str) -> str:
    candidate_rank = _BAND_ORDER.get(candidate_band, 1)
    max_rank = _BAND_ORDER.get(max_band, 1)
    if candidate_rank <= max_rank:
        return candidate_band
    for band, rank in _BAND_ORDER.items():
        if rank == max_rank:
            return band
    return "standard"
