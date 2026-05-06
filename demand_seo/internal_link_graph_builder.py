from __future__ import annotations

class InternalLinkGraphBuilder:
    def build(self, pages: tuple[dict[str, object], ...]) -> dict[str, tuple[str, ...]]:
        slugs = tuple(str(p.get("slug") or "") for p in pages)
        return {slug: tuple(s for s in slugs if s and s != slug) for slug in slugs if slug}
