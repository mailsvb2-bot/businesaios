from __future__ import annotations
CANON_THIN_HANDLER = True
from runtime.product import ProductFeature, RoadmapProposal, build_roadmap_proposal

def handle_product_build(feature: ProductFeature) -> RoadmapProposal:
    return build_roadmap_proposal(feature)
