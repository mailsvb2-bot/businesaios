from __future__ import annotations

from core.world_model.builders.service_support import (
    WorldModelSnapshotSupport,
    WorldModelStateAssembler,
    _NoopPublisher,
)
from core.world_model.builders.world_snapshot_builder import WorldSnapshotBuilder
from core.world_model.contracts import (
    CampaignReader,
    CustomerReader,
    MarketReader,
    MessagingReader,
    ProductReader,
    RevenueReader,
    SnapshotEventPublisher,
    SnapshotRepository,
    WorldSnapshotBuilderPort,
)
from core.world_model.errors import WorldModelGuardError
from core.world_model.evaluators.signal_freshness_evaluator import SignalFreshnessEvaluator
from core.world_model.evaluators.state_completeness_evaluator import StateCompletenessEvaluator
from core.world_model.evaluators.world_confidence_evaluator import WorldConfidenceEvaluator
from core.world_model.guard import WorldModelGuard
from core.world_model.ids import new_snapshot_id
from core.world_model.readers.campaign_reader import DefaultCampaignReader
from core.world_model.readers.customer_reader import DefaultCustomerReader
from core.world_model.readers.market_reader import DefaultMarketReader
from core.world_model.readers.messaging_reader import DefaultMessagingReader
from core.world_model.readers.product_reader import DefaultProductReader
from core.world_model.readers.revenue_reader import DefaultRevenueReader
from core.world_model.repositories.snapshot_repository import InMemorySnapshotRepository
from core.world_model.types import (
    ReaderBundle,
    WorldModelBuildInput,
    WorldModelBuildResult,
    WorldSnapshot,
    WorldSnapshotRequest,
)


class WorldModelService(WorldSnapshotBuilderPort):
    def __init__(
        self,
        *,
        customer_reader: CustomerReader | None = None,
        revenue_reader: RevenueReader | None = None,
        campaign_reader: CampaignReader | None = None,
        product_reader: ProductReader | None = None,
        messaging_reader: MessagingReader | None = None,
        market_reader: MarketReader | None = None,
        repository: SnapshotRepository | None = None,
        publisher: SnapshotEventPublisher | None = None,
        freshness_evaluator: SignalFreshnessEvaluator | None = None,
        completeness_evaluator: StateCompletenessEvaluator | None = None,
        confidence_evaluator: WorldConfidenceEvaluator | None = None,
        guard: WorldModelGuard | None = None,
    ) -> None:
        self._customer_reader = customer_reader or DefaultCustomerReader()
        self._revenue_reader = revenue_reader or DefaultRevenueReader()
        self._campaign_reader = campaign_reader or DefaultCampaignReader()
        self._product_reader = product_reader or DefaultProductReader()
        self._messaging_reader = messaging_reader or DefaultMessagingReader()
        self._market_reader = market_reader or DefaultMarketReader()
        self._repository = repository or InMemorySnapshotRepository()
        self._publisher = publisher or _NoopPublisher()
        self._snapshot_builder = WorldSnapshotBuilder()
        self._freshness_evaluator = freshness_evaluator or SignalFreshnessEvaluator()
        self._completeness_evaluator = completeness_evaluator or StateCompletenessEvaluator()
        self._confidence_evaluator = confidence_evaluator or WorldConfidenceEvaluator()
        self._guard = guard or WorldModelGuard()
        self._state_assembler = WorldModelStateAssembler()
        self._snapshot_support = WorldModelSnapshotSupport()

    def build(self, request: WorldSnapshotRequest) -> WorldSnapshot:
        return self._snapshot_builder.build(request)

    def build_snapshot(self, *, build_input: WorldModelBuildInput) -> WorldModelBuildResult:
        self._guard.validate_build_input(build_input=build_input)
        readers = self._read(build_input=build_input)
        states = self._state_assembler.build_state_bundle(build_input=build_input, readers=readers)
        freshness = self._freshness_evaluator.evaluate(now_ms=build_input.now_ms, readers=readers)
        completeness = self._completeness_evaluator.evaluate(business_state=states.business_state)
        confidence_report = self._confidence_evaluator.evaluate(freshness=freshness, completeness=completeness)
        snapshot_id = new_snapshot_id(tenant_id=build_input.tenant_id, business_id=build_input.business_id)
        built_at_ms = int(build_input.now_ms)
        try:
            self._guard.validate_pre_snapshot(
                business_state=states.business_state,
                freshness=freshness,
                completeness=completeness,
            )
        except WorldModelGuardError as exc:
            return self._reject_build(
                build_input=build_input,
                snapshot_id=snapshot_id,
                built_at_ms=built_at_ms,
                exc=exc,
                freshness=freshness,
                completeness=completeness,
            )
        snapshot = self._build_snapshot(
            build_input=build_input,
            snapshot_id=snapshot_id,
            built_at_ms=built_at_ms,
            readers=readers,
            states=states,
            freshness=freshness,
            completeness=completeness,
            confidence_report=confidence_report,
        )
        snapshot = self._snapshot_support.extend_snapshot_explain(snapshot=snapshot)
        snapshot_built_event = self._snapshot_support.build_snapshot_built_event(snapshot=snapshot)
        snapshot = self._snapshot_support.extend_snapshot_metadata(
            snapshot=snapshot,
            snapshot_built_event=snapshot_built_event,
        )
        self._guard.validate_snapshot(snapshot=snapshot)
        self._repository.put_snapshot(snapshot)
        self._publisher.publish_snapshot_built(snapshot)
        return WorldModelBuildResult(accepted=True, snapshot=snapshot)

    def get_latest_snapshot(self, *, tenant_id: str, business_id: str) -> WorldSnapshot | None:
        return self._repository.get_latest(tenant_id=tenant_id, business_id=business_id)

    def get_snapshot_history(self, *, tenant_id: str, business_id: str) -> list[WorldSnapshot]:
        return self._repository.get_history(tenant_id=tenant_id, business_id=business_id)

    def _read(self, *, build_input: WorldModelBuildInput) -> ReaderBundle:
        return ReaderBundle(
            customer=self._customer_reader.read(build_input=build_input),
            revenue=self._revenue_reader.read(build_input=build_input),
            campaign=self._campaign_reader.read(build_input=build_input),
            product=self._product_reader.read(build_input=build_input),
            messaging=self._messaging_reader.read(build_input=build_input),
            market=self._market_reader.read(build_input=build_input),
        )

    def _build_snapshot(
        self,
        *,
        build_input: WorldModelBuildInput,
        snapshot_id: str,
        built_at_ms: int,
        readers: ReaderBundle,
        states,
        freshness,
        completeness,
        confidence_report,
    ) -> WorldSnapshot:
        request = WorldSnapshotRequest(
            tenant_id=build_input.tenant_id,
            correlation_id=build_input.correlation_id or snapshot_id,
        )
        return self._snapshot_builder.build(
            request,
            business_id=build_input.business_id,
            snapshot_id=snapshot_id,
            built_at_ms=built_at_ms,
            business_state=states.business_state,
            freshness=freshness,
            completeness=completeness,
            confidence_report=confidence_report,
            explain=self._snapshot_support.build_explain(
                freshness=freshness,
                completeness=completeness,
                confidence_report=confidence_report,
            ),
            metadata=self._snapshot_support.build_metadata(readers=readers),
        )

    def _reject_build(
        self,
        *,
        build_input: WorldModelBuildInput,
        snapshot_id: str,
        built_at_ms: int,
        exc: WorldModelGuardError,
        freshness,
        completeness,
    ) -> WorldModelBuildResult:
        rejection_event = self._snapshot_support.build_snapshot_rejected_event(
            snapshot_id=snapshot_id,
            tenant_id=build_input.tenant_id,
            business_id=build_input.business_id,
            built_at_ms=built_at_ms,
            exc=exc,
            freshness=freshness,
            completeness=completeness,
        )
        rejection = self._snapshot_support.build_rejection(
            build_input=build_input,
            snapshot_id=snapshot_id,
            built_at_ms=built_at_ms,
            exc=exc,
            freshness=freshness,
            completeness=completeness,
            rejection_event=rejection_event,
        )
        self._repository.put_rejection(rejection)
        self._publisher.publish_snapshot_rejected(rejection)
        return WorldModelBuildResult(accepted=False, rejection=rejection)



def build_world_snapshot(builder: WorldSnapshotBuilderPort, request: WorldSnapshotRequest) -> WorldSnapshot:
    return builder.build(request)
