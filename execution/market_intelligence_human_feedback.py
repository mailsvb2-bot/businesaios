from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
from typing import Any

from execution.market_intelligence_advanced_models import HumanFeedbackEvent


CANON_MARKET_INTELLIGENCE_HUMAN_FEEDBACK = True


def _safe_key(value: object) -> str:
    return ''.join(ch if ch.isalnum() or ch in {'-', '_'} else '_' for ch in str(value or '').strip() or 'unknown')


@dataclass
class HumanFeedbackStore:
    root_dir: Path = Path('.runtime_data/market_intelligence/human_feedback')

    def append(self, event: HumanFeedbackEvent) -> None:
        path = self.root_dir / _safe_key(event.tenant_id) / f'{_safe_key(event.entity_id)}.jsonl'
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps({'tenant_id': event.tenant_id, 'entity_id': event.entity_id, 'label': event.label, 'score_delta': event.score_delta, 'is_false_positive': event.is_false_positive, 'tags': list(event.tags), 'feedback_at': event.feedback_at, 'metadata': dict(event.metadata)}, ensure_ascii=False) + '\n')

    def load(self, *, tenant_id: str, entity_id: str) -> tuple[HumanFeedbackEvent, ...]:
        path = self.root_dir / _safe_key(tenant_id) / f'{_safe_key(entity_id)}.jsonl'
        if not path.exists():
            return ()
        events: list[HumanFeedbackEvent] = []
        for line in path.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if isinstance(payload, dict):
                events.append(HumanFeedbackEvent(**payload))
        return tuple(events)


@dataclass
class HumanFeedbackLoop:
    store: HumanFeedbackStore = field(default_factory=HumanFeedbackStore)

    def record(self, event: HumanFeedbackEvent) -> None:
        self.store.append(event)

    def summarize(self, *, tenant_id: str, entity_id: str) -> dict[str, Any]:
        events = self.store.load(tenant_id=tenant_id, entity_id=entity_id)
        score_delta = sum(item.score_delta for item in events)
        false_positives = sum(1 for item in events if item.is_false_positive)
        tags = sorted({tag for item in events for tag in item.tags})
        return {
            'tenant_id': tenant_id,
            'entity_id': entity_id,
            'events_count': len(events),
            'score_delta': max(-1.0, min(score_delta, 1.0)),
            'false_positives': false_positives,
            'tags': tags,
        }


__all__ = ['CANON_MARKET_INTELLIGENCE_HUMAN_FEEDBACK', 'HumanFeedbackLoop', 'HumanFeedbackStore']
