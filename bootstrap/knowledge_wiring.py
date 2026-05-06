from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True


from contracts.event_store import EventStore

from runtime.knowledge import (
    BusinessCaseBuilder,
    CampaignOutcomeLessonDraftMapper,
    EventStoreLessonRepository,
    EventStoreMemoryLinkRepository,
    EventStorePatternRepository,
    ExperimentOutcomeLessonDraftMapper,
    IncidentLessonDraftMapper,
    KnowledgeCommandService,
    KnowledgeExplainService,
    KnowledgeGuard,
    KnowledgeQueryService,
    LessonBuilder,
    LessonDeduplicator,
    LessonDraftIngestionAdapter,
    LessonReader,
    LessonRelevanceEvaluator,
    LessonUsageExplainer,
    LessonWriter,
    MemoryLinkWriter,
    MemorySummaryBuilder,
    MemoryTraceExplainer,
    PatternBuilder,
    PatternConfidenceEvaluator,
    PatternConfidenceExplainer,
    PatternReader,
    PatternWriter,
    RetrievalQualityEvaluator,
    StaleMemoryGuard,
    StrategyMemoryReader,
    UnsafeReuseGuard,
    WeakPatternGuard,
)
from bootstrap.knowledge_bundle import KnowledgeRuntimeBundle
from bootstrap.knowledge_event_publisher import InMemoryKnowledgeEventPublisher


def build_knowledge_runtime_bundle(*, event_store: EventStore, tenant_id: str) -> KnowledgeRuntimeBundle:
    lesson_repository = EventStoreLessonRepository(event_store=event_store, tenant_id=tenant_id)
    pattern_repository = EventStorePatternRepository(event_store=event_store, tenant_id=tenant_id)
    memory_link_repository = EventStoreMemoryLinkRepository(event_store=event_store, tenant_id=tenant_id)

    lesson_builder = LessonBuilder()
    pattern_builder = PatternBuilder()
    lesson_relevance_evaluator = LessonRelevanceEvaluator()
    retrieval_quality_evaluator = RetrievalQualityEvaluator()
    pattern_confidence_evaluator = PatternConfidenceEvaluator()

    lesson_writer = LessonWriter(builder=lesson_builder, repository=lesson_repository)
    pattern_writer = PatternWriter(builder=pattern_builder, repository=pattern_repository)
    memory_link_writer = MemoryLinkWriter(repository=memory_link_repository)

    lesson_reader = LessonReader(repository=lesson_repository)
    pattern_reader = PatternReader(repository=pattern_repository)
    strategy_memory_reader = StrategyMemoryReader(
        lesson_repository=lesson_repository,
        pattern_repository=pattern_repository,
        lesson_relevance_evaluator=lesson_relevance_evaluator,
    )

    knowledge_guard = KnowledgeGuard(
        stale_memory_guard=StaleMemoryGuard(),
        weak_pattern_guard=WeakPatternGuard(),
        unsafe_reuse_guard=UnsafeReuseGuard(),
    )

    memory_summary_builder = MemorySummaryBuilder(retrieval_quality_evaluator=retrieval_quality_evaluator)
    business_case_builder = BusinessCaseBuilder()
    event_publisher = InMemoryKnowledgeEventPublisher()

    command_service = KnowledgeCommandService(
        lesson_writer=lesson_writer,
        pattern_writer=pattern_writer,
        memory_link_writer=memory_link_writer,
        event_publisher=event_publisher,
    )
    query_service = KnowledgeQueryService(
        strategy_memory_reader=strategy_memory_reader,
        knowledge_guard=knowledge_guard,
        memory_summary_builder=memory_summary_builder,
        lesson_reader=lesson_reader,
        pattern_reader=pattern_reader,
        business_case_builder=business_case_builder,
        event_publisher=event_publisher,
    )
    explain_service = KnowledgeExplainService(
        query_service=query_service,
        lesson_reader=lesson_reader,
        pattern_reader=pattern_reader,
        lesson_relevance_evaluator=lesson_relevance_evaluator,
        pattern_confidence_evaluator=pattern_confidence_evaluator,
        memory_trace_explainer=MemoryTraceExplainer(),
        lesson_usage_explainer=LessonUsageExplainer(),
        pattern_confidence_explainer=PatternConfidenceExplainer(),
    )
    ingestion_adapter = LessonDraftIngestionAdapter(
        experiment_mapper=ExperimentOutcomeLessonDraftMapper(),
        incident_mapper=IncidentLessonDraftMapper(),
        campaign_mapper=CampaignOutcomeLessonDraftMapper(),
    )
    deduplicator = LessonDeduplicator()
    return KnowledgeRuntimeBundle(
        command_service=command_service,
        query_service=query_service,
        explain_service=explain_service,
        ingestion_adapter=ingestion_adapter,
        deduplicator=deduplicator,
    )
