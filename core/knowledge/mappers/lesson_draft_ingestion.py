from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ..types import LessonDraft
from .campaign_outcome_lesson_draft_mapper import CampaignOutcomeLessonDraftMapper
from .experiment_outcome_lesson_draft_mapper import ExperimentOutcomeLessonDraftMapper
from .incident_lesson_draft_mapper import IncidentLessonDraftMapper


@dataclass(frozen=True)
class LessonDraftIngestionAdapter:
    experiment_mapper: ExperimentOutcomeLessonDraftMapper
    incident_mapper: IncidentLessonDraftMapper
    campaign_mapper: CampaignOutcomeLessonDraftMapper

    def from_experiment_outcome(self, payload: Mapping[str, object]) -> LessonDraft:
        return self.experiment_mapper.map(payload)

    def from_incident(self, payload: Mapping[str, object]) -> LessonDraft:
        return self.incident_mapper.map(payload)

    def from_campaign_outcome(self, payload: Mapping[str, object]) -> LessonDraft:
        return self.campaign_mapper.map(payload)
