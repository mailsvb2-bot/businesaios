from __future__ import annotations

from runtime.product import ProductFeature, RoadmapProposal, build_roadmap_proposal

CANON_THIN_HANDLER = True

def handle_product_build(feature: ProductFeature) -> RoadmapProposal:
    return build_roadmap_proposal(feature)
