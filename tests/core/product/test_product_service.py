from __future__ import annotations

from core.product.enums import FeatureStatus, FeatureType, ProposalStatus
from core.product.readers.feature_reader import InMemoryFeatureReader
from core.product.readers.roadmap_reader import InMemoryRoadmapReader
from core.product.repositories.packaging_repository import PackagingRepository
from core.product.repositories.roadmap_repository import RoadmapRepository
from core.product.service import ProductService
from core.product.types import FeatureRecord, RoadmapCapacity
from core.product.writers.feature_writer import InMemoryFeatureWriter
from core.product.writers.packaging_writer import InMemoryPackagingWriter
from core.product.writers.roadmap_writer import InMemoryRoadmapWriter


def _build_service(features: list[FeatureRecord], capacity: RoadmapCapacity | None = None) -> ProductService:
    return ProductService(
        feature_reader=InMemoryFeatureReader({"prod-1": features}),
        roadmap_reader=InMemoryRoadmapReader({"prod-1": capacity or RoadmapCapacity(1, 2, 3)}),
        feature_writer=InMemoryFeatureWriter(),
        roadmap_writer=InMemoryRoadmapWriter(),
        packaging_writer=InMemoryPackagingWriter(),
        roadmap_repository=RoadmapRepository(),
        packaging_repository=PackagingRepository(),
    )


def test_product_service_builds_advisory_roadmap() -> None:
    service = _build_service(
        [
            FeatureRecord(
                feature_id="f1",
                name="Onboarding",
                feature_type=FeatureType.ACTIVATION,
                status=FeatureStatus.READY,
                adoption_rate=0.30,
                retention_delta=0.12,
                revenue_delta=0.05,
                effort_points=2.0,
                risk_score=1.0,
            ),
            FeatureRecord(
                feature_id="f2",
                name="Workspace seats",
                feature_type=FeatureType.REVENUE,
                status=FeatureStatus.RELEASED,
                adoption_rate=0.20,
                retention_delta=0.04,
                revenue_delta=0.18,
                effort_points=4.0,
                risk_score=1.0,
            ),
        ]
    )

    proposal, projection, events = service.build_roadmap_proposal("prod-1")

    assert proposal.executable is False
    assert proposal.mode.value == "advisory"
    assert proposal.status == ProposalStatus.DRAFT
    assert "roadmap" in projection
    assert len(events) >= 1


def test_product_service_builds_packaging_advisory_only() -> None:
    service = _build_service(
        [
            FeatureRecord(
                feature_id="a",
                name="Core",
                feature_type=FeatureType.EXPERIENCE,
                status=FeatureStatus.READY,
                adoption_rate=0.30,
                retention_delta=0.02,
                revenue_delta=0.01,
                effort_points=1.0,
                risk_score=0.1,
            ),
            FeatureRecord(
                feature_id="b",
                name="Heavy",
                feature_type=FeatureType.REVENUE,
                status=FeatureStatus.READY,
                adoption_rate=0.01,
                retention_delta=0.01,
                revenue_delta=0.20,
                effort_points=9.0,
                risk_score=1.0,
            ),
        ]
    )

    proposal, events = service.build_packaging_proposal("prod-1")

    assert proposal.executable is False
    assert proposal.mode.value == "advisory"
    assert proposal.status in {ProposalStatus.DRAFT, ProposalStatus.BLOCKED}
    assert isinstance(events, list)
