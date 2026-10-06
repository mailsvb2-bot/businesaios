from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from contracts.landing_page import EventLandingContent


CANON_EVENT_LANDING_LIFECYCLE = True


class EventLandingPublicationStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


@dataclass(frozen=True, slots=True)
class EventLandingState:
    """Canonical event-landing lifecycle state.

    This is deliberately storage-agnostic. Durable persistence belongs to the
    existing BusinessAIOS Artifact/Event owners; this module owns only the
    deterministic transition semantics absorbed from the donor product.
    """

    event_id: str
    draft: EventLandingContent
    draft_source: str
    revision: int = 1
    status: EventLandingPublicationStatus = EventLandingPublicationStatus.DRAFT
    published_revision: int | None = None
    published: EventLandingContent | None = None

    def __post_init__(self) -> None:
        event_id = str(self.event_id or "").strip()
        if not event_id or len(event_id) > 200:
            raise ValueError("event_id must be 1..200 characters")
        object.__setattr__(self, "event_id", event_id)
        source = str(self.draft_source or "").strip()
        if source not in {"template", "manual", "ai"}:
            raise ValueError("draft_source must be template, manual or ai")
        object.__setattr__(self, "draft_source", source)
        revision = int(self.revision)
        if revision < 1:
            raise ValueError("revision must be >= 1")
        object.__setattr__(self, "revision", revision)
        status = EventLandingPublicationStatus(self.status)
        object.__setattr__(self, "status", status)
        if self.published_revision is not None:
            published_revision = int(self.published_revision)
            if published_revision < 1 or published_revision > revision:
                raise ValueError("published_revision must be within the revision history")
            object.__setattr__(self, "published_revision", published_revision)
        if (self.published_revision is None) != (self.published is None):
            raise ValueError("published content and published_revision must exist together")
        if status is EventLandingPublicationStatus.PUBLISHED and self.published is None:
            raise ValueError("published status requires a published snapshot")

    @property
    def is_published(self) -> bool:
        return self.status is EventLandingPublicationStatus.PUBLISHED

    @property
    def has_unpublished_changes(self) -> bool:
        return self.published_revision is not None and self.published_revision != self.revision

    def preview(self) -> EventLandingContent:
        """Preview is always the current draft and never mutates publication state."""
        return self.draft

    def save_draft(
        self,
        *,
        content: EventLandingContent,
        source: str,
        expected_revision: int,
    ) -> "EventLandingState":
        self._require_revision(expected_revision)
        return EventLandingState(
            event_id=self.event_id,
            draft=content,
            draft_source=source,
            revision=self.revision + 1,
            status=self.status,
            published_revision=self.published_revision,
            published=self.published,
        )

    def publish(self, *, expected_revision: int) -> "EventLandingState":
        self._require_revision(expected_revision)
        return EventLandingState(
            event_id=self.event_id,
            draft=self.draft,
            draft_source=self.draft_source,
            revision=self.revision,
            status=EventLandingPublicationStatus.PUBLISHED,
            published_revision=self.revision,
            published=self.draft,
        )

    def unpublish(self, *, expected_revision: int) -> "EventLandingState":
        self._require_revision(expected_revision)
        return EventLandingState(
            event_id=self.event_id,
            draft=self.draft,
            draft_source=self.draft_source,
            revision=self.revision,
            status=EventLandingPublicationStatus.DRAFT,
            published_revision=None,
            published=None,
        )

    def public_content(self) -> EventLandingContent | None:
        """Return only an explicitly published snapshot, never an unpublished draft."""
        if not self.is_published:
            return None
        return self.published

    def _require_revision(self, expected_revision: int) -> None:
        if isinstance(expected_revision, bool) or int(expected_revision) != self.revision:
            raise RuntimeError("event_landing_revision_conflict")


def new_event_landing_state(
    *,
    event_id: str,
    content: EventLandingContent,
    source: str = "template",
) -> EventLandingState:
    return EventLandingState(
        event_id=event_id,
        draft=content,
        draft_source=source,
        revision=1,
    )


__all__ = [
    "CANON_EVENT_LANDING_LIFECYCLE",
    "EventLandingPublicationStatus",
    "EventLandingState",
    "new_event_landing_state",
]
