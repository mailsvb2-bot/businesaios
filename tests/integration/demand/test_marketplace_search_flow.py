from __future__ import annotations

from marketplace.search import SearchRanker
from supply_directory.business_directory import BusinessDirectory


def test_marketplace_search_flow():
    directory = BusinessDirectory(); directory.seed_defaults()
    ranked = SearchRanker().rank(directory.list_profiles())
    assert ranked
