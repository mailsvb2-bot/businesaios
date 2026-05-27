from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from application.evidence.evidence_roundtrip import EvidenceRoundtripVerifier
from application.governance.canonical_governance_decision import (
    canonical_baseline_selection_decision,
    canonical_promotion_decision,
    canonical_rollback_recommendation_decision,
)
from application.governance.canonical_governance_evidence import canonical_governance_evidence
from application.governance.canonical_governance_timeline import canonical_governance_timeline
from application.governance.canonical_scenario_governance import (
    canonical_scenario_catalog_entry,
    canonical_scenario_selection_outcome,
)
from application.memory.business_memory_governance import BusinessMemoryGovernanceGate
from application.memory.business_memory_promotion import BusinessMemoryPromotionHelper
from application.memory.business_memory_query import BusinessMemoryQueryService
from application.memory.business_operating_memory import (
    BusinessMemoryCompactor,
    BusinessMemoryPolicy,
    FileBusinessOperatingMemoryStore,
    project_business_memory_governance_summary,
)
from execution.baseline_history import FileBaselineHistoryStore
from execution.baseline_manager import FileBaselineStore
from execution.baseline_rollback import BaselineRollbackManager, FileBaselineRollbackStore
from execution.baseline_selector import BaselineSelector
from execution.drift_audit_report import DriftAuditReportBuilder
from execution.drift_detector import DriftDetector
from execution.drift_history_joiner import DriftHistoryJoiner
from execution.drift_trend_tracker import DriftTrendTracker
from execution.headless_ledger import FileHeadlessLedger
from execution.headless_paths import build_headless_runtime_paths
from execution.promotion_gate import PromotionGate
from execution.rollback_audit_timeline import RollbackAuditTimelineBuilder
from execution.rollback_recommender import MemoryAwareRollbackRecommender
from execution.run_diff_builder import RunDiffBuilder
from execution.run_selector import RunSelector
from execution.scenario_baseline_catalog import FileScenarioBaselineCatalog
from execution.scenario_baseline_namespace import ScenarioBaselineNamespace

CANON_HEADLESS_GOVERNANCE_SERVICE = True

@dataclass
class GovernanceService:
    ledger: FileHeadlessLedger
    business_memory: FileBusinessOperatingMemoryStore
    business_memory_query: BusinessMemoryQueryService
    baselines: FileBaselineStore
    business_memory_gate: BusinessMemoryGovernanceGate
    business_memory_promotion: BusinessMemoryPromotionHelper
    history: FileBaselineHistoryStore
    rollback_manager: BaselineRollbackManager
    baseline_selector: BaselineSelector
    drift_detector: DriftDetector
    diff_builder: RunDiffBuilder
    drift_audit_builder: DriftAuditReportBuilder
    rollback_timeline_builder: RollbackAuditTimelineBuilder
    drift_trend_tracker: DriftTrendTracker
    rollback_recommender: MemoryAwareRollbackRecommender
    drift_history_joiner: DriftHistoryJoiner
    evidence_roundtrip: EvidenceRoundtripVerifier
    scenario_namespace: ScenarioBaselineNamespace
    scenario_catalog: FileScenarioBaselineCatalog

    @classmethod
    def build_default(cls, *, root_dir: str | Path | None = None) -> 'GovernanceService':
        paths = build_headless_runtime_paths(root_dir=root_dir)
        history = FileBaselineHistoryStore(root_dir=paths.headless_baseline_history_dir)
        baselines = FileBaselineStore(root_dir=paths.headless_baselines_dir, history_store=history)
        memory_policy = BusinessMemoryPolicy()
        business_memory = FileBusinessOperatingMemoryStore(root_dir=paths.business_operating_memory_dir, policy=memory_policy, compactor=BusinessMemoryCompactor(policy=memory_policy))
        return cls(
            ledger=FileHeadlessLedger(root_dir=paths.headless_ledger_dir),
            business_memory=business_memory,
            business_memory_query=BusinessMemoryQueryService(store=business_memory),
            business_memory_gate=BusinessMemoryGovernanceGate(),
            business_memory_promotion=BusinessMemoryPromotionHelper(),
            baselines=baselines,
            history=history,
            rollback_manager=BaselineRollbackManager(rollback_store=FileBaselineRollbackStore(root_dir=paths.headless_baseline_rollbacks_dir), history_store=history),
            baseline_selector=BaselineSelector(promotion_gate=PromotionGate(), run_selector=RunSelector()),
            drift_detector=DriftDetector(),
            diff_builder=RunDiffBuilder(),
            drift_audit_builder=DriftAuditReportBuilder(),
            rollback_timeline_builder=RollbackAuditTimelineBuilder(),
            drift_trend_tracker=DriftTrendTracker(),
            rollback_recommender=MemoryAwareRollbackRecommender(),
            drift_history_joiner=DriftHistoryJoiner(),
            evidence_roundtrip=EvidenceRoundtripVerifier(),
            scenario_namespace=ScenarioBaselineNamespace(),
            scenario_catalog=FileScenarioBaselineCatalog(root_dir=paths.scenario_baseline_catalog_dir),
        )

    def business_memory_summary(self, *, tenant_id: str, business_id: str) -> dict[str, Any]:
        return project_business_memory_governance_summary(
            self.business_memory_query.get_summary(tenant_id=tenant_id, business_id=business_id)
        )

    def memory_summary(self, *, tenant_id: str, business_id: str) -> dict[str, Any]:
        return self.business_memory_summary(tenant_id=tenant_id, business_id=business_id)

    def promote_baseline(self, *, baseline_name: str, run_id: str, label: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        record = self.ledger.read(run_id)
        memory_summary = self.business_memory_summary(tenant_id=str(record.get('tenant_id') or 'default'), business_id=str(record.get('business_id') or ''))
        fit_report = self.business_memory_gate.evaluate(candidate_record=record, business_memory_summary=memory_summary)
        promotion_evidence = self.business_memory_promotion.build_promotion_evidence(
            candidate_record=record,
            business_memory_summary=memory_summary,
            fit_report=fit_report,
            baseline_name=baseline_name,
            metadata=dict(metadata or {}),
        )
        promotion_decision = canonical_promotion_decision(
            baseline_name=baseline_name,
            candidate_record=record,
            label=label,
            fit_report=fit_report,
            governance_evidence=promotion_evidence.get('governance_evidence') or {},
            metadata=dict(metadata or {}),
        )
        combined_metadata = {**dict(metadata or {}), **promotion_evidence, **promotion_decision}
        self.baselines.promote(baseline_name=baseline_name, record=record, promoted_at_label=label, metadata=combined_metadata)
        promoted = self.baselines.read(baseline_name=baseline_name)
        promoted['governance_decision'] = dict(promoted.get('metadata', {}).get('governance_decision') or {})
        return promoted

    def select_baseline(self, *, run_ids: list[str], baseline_name: str = '') -> dict[str, Any] | None:
        records = [self.ledger.read(run_id) for run_id in run_ids]
        selected, decision = self.baseline_selector.choose_with_decision(records=records, baseline_name=baseline_name)
        if selected is None:
            return None
        enriched = dict(selected)
        enriched['governance_decision'] = dict(decision.get('governance_decision') or {})
        return enriched

    def promote_best_for_scenario(self, *, scenario: str, run_ids: list[str], suffix: str = 'golden', label: str = 'scenario_auto', metadata: dict[str, Any] | None = None) -> dict[str, Any] | None:
        selected = self.select_baseline(run_ids=run_ids, baseline_name=self.scenario_namespace.name_for(scenario=scenario, suffix=suffix))
        if not selected:
            return None
        baseline_name = self.scenario_namespace.name_for(scenario=scenario, suffix=suffix)
        memory_summary = self.business_memory_summary(tenant_id=str(selected.get('tenant_id') or 'default'), business_id=str(selected.get('business_id') or ''))
        fit_report = self.business_memory_gate.evaluate(candidate_record=selected, business_memory_summary=memory_summary)
        scenario_alignment = self.business_memory_promotion.scenario_alignment(scenario=scenario, business_memory_summary=memory_summary)
        promoted = self.promote_baseline(
            baseline_name=baseline_name,
            run_id=str(selected.get('run_id') or ''),
            label=label,
            metadata={
                'scenario': str(scenario),
                'scenario_memory_alignment': {
                    'scenario': scenario_alignment.scenario,
                    'aligned': scenario_alignment.aligned,
                    'score': scenario_alignment.score,
                    'reasons': list(scenario_alignment.reasons),
                },
                'business_memory_fit': {
                    'approved': fit_report.approved,
                    'score': fit_report.score,
                    'reasons': list(fit_report.reasons),
                    'summary': fit_report.summary,
                },
                **dict(metadata or {}),
            },
        )
        self.scenario_catalog.put(scenario=scenario, baseline_name=baseline_name, source_run_id=str(selected.get('run_id') or ''), metadata={'label': label, 'scenario': str(scenario)})
        scenario_entry = self.scenario_catalog.get(scenario=scenario)
        scenario_outcome = canonical_scenario_selection_outcome(
            scenario=scenario,
            baseline_name=baseline_name,
            selected_record=selected,
            governance_decision=selected.get('governance_decision') or {},
            catalog_entry=scenario_entry,
            metadata={'label': label, **dict(metadata or {})},
        )
        promoted['scenario_governance'] = dict(scenario_outcome.get('scenario_governance') or {})
        promoted['metadata'] = {**dict(promoted.get('metadata') or {}), 'scenario_governance': dict(scenario_outcome.get('scenario_governance') or {})}
        return promoted

    def audit_drift(self, *, baseline_name: str, candidate_run_id: str) -> dict[str, Any]:
        baseline = self.baselines.read(baseline_name=baseline_name)
        candidate = self.ledger.read(candidate_run_id)
        drift = self.drift_detector.detect(baseline=baseline, candidate=candidate)
        diff = self.diff_builder.build(left=dict(baseline.get('record') or {}), right=candidate)
        report_text = self.drift_audit_builder.build(baseline_name=baseline_name, baseline=baseline, candidate=candidate, drift=drift, diff=diff)
        memory_summary = self.business_memory_summary(tenant_id=str(candidate.get('tenant_id') or 'default'), business_id=str(candidate.get('business_id') or ''))
        fit_report = self.business_memory_gate.evaluate(candidate_record=candidate, business_memory_summary=memory_summary)
        governance_evidence = canonical_governance_evidence(
            governance_action='audit_drift',
            baseline_name=baseline_name,
            candidate_record=candidate,
            baseline_record=baseline,
            business_memory_summary=memory_summary,
            fit_report=fit_report,
            drift_payload={
                'severity': drift.severity,
                'goal_score_delta': float(drift.goal_score_delta),
                'report_text': report_text,
                'changed_fields': list(diff.changed_fields),
                'left_only_events': list(diff.left_only_events),
                'right_only_events': list(diff.right_only_events),
            },
        )
        return {
            'baseline_name': baseline_name,
            'candidate_run_id': candidate_run_id,
            'severity': drift.severity,
            'goal_score_delta': float(drift.goal_score_delta),
            'report_text': report_text,
            'changed_fields': list(diff.changed_fields),
            'left_only_events': list(diff.left_only_events),
            'right_only_events': list(diff.right_only_events),
            'business_memory_summary': memory_summary,
            'business_memory_fit': {
                'approved': fit_report.approved,
                'score': fit_report.score,
                'reasons': list(fit_report.reasons),
                'summary': fit_report.summary,
            },
            'governance_evidence': governance_evidence,
        }

    def rollback_baseline(self, *, baseline_name: str, fallback_run_id: str, reason: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        baseline = self.baselines.read(baseline_name=baseline_name)
        fallback = self.ledger.read(fallback_run_id)
        memory_summary = self.business_memory_summary(tenant_id=str(fallback.get('tenant_id') or 'default'), business_id=str(fallback.get('business_id') or ''))
        fit_report = self.business_memory_gate.evaluate(candidate_record=fallback, business_memory_summary=memory_summary)
        governance_evidence = canonical_governance_evidence(
            governance_action='rollback_baseline',
            baseline_name=baseline_name,
            candidate_record=fallback,
            baseline_record=baseline,
            business_memory_summary=memory_summary,
            fit_report=fit_report,
            rollback_payload={
                'previous_source_run_id': str(baseline.get('source_run_id') or ''),
                'new_source_run_id': str(fallback.get('run_id') or ''),
                'reason': str(reason),
                'metadata': dict(metadata or {}),
            },
            metadata=dict(metadata or {}),
        )
        return self.rollback_manager.rollback(
            baseline_store=self.baselines,
            baseline_name=baseline_name,
            fallback_record=fallback,
            reason=reason,
            metadata={**dict(metadata or {}), 'governance_evidence': governance_evidence},
        )

    def rollback_timeline(self, *, baseline_name: str) -> str:
        rollback_record = self.rollback_manager.rollback_store.read(baseline_name=baseline_name)
        history_rows = self.history.read_all(baseline_name=baseline_name)
        return self.rollback_timeline_builder.build(baseline_name=baseline_name, rollback_record=rollback_record, history_rows=history_rows)

    def drift_trend(self, *, baseline_name: str, candidate_run_ids: list[str]) -> dict[str, Any]:
        baseline = self.baselines.read(baseline_name=baseline_name)
        reports = [self.drift_detector.detect(baseline=baseline, candidate=self.ledger.read(run_id)) for run_id in candidate_run_ids]
        summary = self.drift_trend_tracker.summarize(drift_reports=reports)
        return {
            'baseline_name': baseline_name,
            'samples': summary.samples,
            'avg_goal_score_delta': float(summary.avg_goal_score_delta),
            'high_count': summary.high_count,
            'medium_count': summary.medium_count,
            'low_count': summary.low_count,
            'none_count': summary.none_count,
            'summary': summary.summary,
        }

    def rollback_recommendation(self, *, baseline_name: str, candidate_run_id: str, fallback_run_ids: list[str]) -> dict[str, Any]:
        baseline = self.baselines.read(baseline_name=baseline_name)
        candidate = self.ledger.read(candidate_run_id)
        drift_payload = self.audit_drift(baseline_name=baseline_name, candidate_run_id=candidate_run_id)
        memory_summary = self.business_memory_summary(tenant_id=str(candidate.get('tenant_id') or 'default'), business_id=str(candidate.get('business_id') or ''))
        fallback_candidates = [self.ledger.read(run_id) for run_id in fallback_run_ids]
        recommendation = self.rollback_recommender.recommend(candidate_record=candidate, baseline_record=baseline, drift_payload=drift_payload, business_memory_summary=memory_summary, fallback_candidates=fallback_candidates)
        governance_evidence = canonical_governance_evidence(
            governance_action='rollback_recommendation',
            baseline_name=baseline_name,
            candidate_record=candidate,
            baseline_record=baseline,
            business_memory_summary=memory_summary,
            fit_report=drift_payload.get('business_memory_fit') or {},
            drift_payload=drift_payload,
            rollback_payload={
                'reason': recommendation.reason,
                'new_source_run_id': recommendation.recommended_run_id,
            },
        )
        governance_decision = canonical_rollback_recommendation_decision(
            baseline_name=baseline_name,
            candidate_run_id=candidate_run_id,
            recommendation=recommendation,
            governance_evidence=governance_evidence,
            metadata={'fallback_run_ids': list(fallback_run_ids)},
        )
        return {
            'baseline_name': baseline_name,
            'candidate_run_id': candidate_run_id,
            'should_rollback': recommendation.should_rollback,
            'confidence': recommendation.confidence,
            'reason': recommendation.reason,
            'recommended_run_id': recommendation.recommended_run_id,
            'governance_evidence': governance_evidence,
            'governance_decision': dict(governance_decision.get('governance_decision') or {}),
        }

    def joined_history(self, *, baseline_name: str, candidate_run_ids: list[str]) -> dict[str, Any]:
        history_rows = self.history.read_all(baseline_name=baseline_name)
        try:
            rollback_record = self.rollback_manager.rollback_store.read(baseline_name=baseline_name)
        except Exception:
            rollback_record = None
        drift_reports = [self.audit_drift(baseline_name=baseline_name, candidate_run_id=run_id) for run_id in candidate_run_ids]
        baseline = self.baselines.read(baseline_name=baseline_name)
        joined = self.drift_history_joiner.build(baseline_name=baseline_name, history_rows=history_rows, rollback_record=rollback_record, drift_reports=drift_reports)
        return canonical_governance_timeline(
            baseline_name=baseline_name,
            baseline_snapshot=baseline,
            history_rows=list(joined.get('history_rows') or history_rows),
            rollback_record=joined.get('rollback_record') if isinstance(joined, dict) else rollback_record,
            drift_reports=list(joined.get('drift_reports') or drift_reports) if isinstance(joined, dict) else drift_reports,
        )

    def verify_promotion_evidence(self, *, baseline_name: str) -> dict[str, Any]:
        payload = self.baselines.read(baseline_name=baseline_name)
        record = dict(payload.get('record') or {})
        memory_summary = self.business_memory_summary(tenant_id=str(record.get('tenant_id') or 'default'), business_id=str(record.get('business_id') or ''))
        metadata = dict(payload.get('metadata') or {})
        governance_evidence = dict(metadata.get('governance_evidence') or {})
        if not governance_evidence:
            governance_evidence = canonical_governance_evidence(
                governance_action='verify_promotion_evidence',
                baseline_name=baseline_name,
                candidate_record=record,
                baseline_record=payload,
                business_memory_summary=memory_summary,
                fit_report=metadata.get('business_memory_fit') or {},
                scenario_alignment=metadata.get('scenario_memory_alignment') or {},
                metadata=metadata,
            )
            metadata = {**metadata, 'governance_evidence': governance_evidence}
        return self.evidence_roundtrip.verify(memory_summary=memory_summary, governance_payload=metadata)

__all__ = ['CANON_HEADLESS_GOVERNANCE_SERVICE', 'GovernanceService']
