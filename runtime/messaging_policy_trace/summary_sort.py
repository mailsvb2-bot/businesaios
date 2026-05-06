from __future__ import annotations


def sort_summaries_desc(items):
    return tuple(sorted(items, key=lambda x: str(x.updated_at or ''), reverse=True))
