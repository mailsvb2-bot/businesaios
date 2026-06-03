from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping

CANON_CHANNEL_ROI_MEMORY = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _text(value: object) -> str:
    return str(value or "").strip()


@dataclass(frozen=True, slots=True)
class ChannelROISnapshot:
    channel: str
    action_type: str
    verified_samples: int = 0
    unverified_samples: int = 0
    average_expected_roi: float = 0.0
    average_realized_revenue: float = 0.0
    positive_roi_rate: float = 0.0
    confidence_hint: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "action_type": self.action_type,
            "verified_samples": int(self.verified_samples),
            "unverified_samples": int(self.unverified_samples),
            "average_expected_roi": float(self.average_expected_roi),
            "average_realized_revenue": float(self.average_realized_revenue),
            "positive_roi_rate": float(self.positive_roi_rate),
            "confidence_hint": float(self.confidence_hint),
            "metadata": dict(self.metadata),
        }


class ChannelROIMemory:
    """
    Read-only channel ROI summarizer.

    Important:
    - Not a decision module.
    - Does not mutate business memory.
    - Summarizes already persisted factual economic feedback.
    """

    def from_records(
        self,
        *,
        channel: str,
        action_type: str,
        records: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    ) -> ChannelROISnapshot:
        filtered: list[dict[str, Any]] = []
        for record in records:
            payload = _safe_dict(record)
            if _text(payload.get("kind")) not in {"economic_feedback", "economic_memory_feedback"}:
                continue
            record_channel = _text(payload.get("channel"))
            record_action = _text(payload.get("action_type"))
            if record_channel and record_channel != channel:
                continue
            if record_action and record_action != action_type:
                continue
            filtered.append(payload)

        verified_samples = sum(1 for item in filtered if _safe_bool(item.get("verified")))
        unverified_samples = max(0, len(filtered) - verified_samples)
        expected_roi_values = [_safe_float(item.get("expected_roi")) for item in filtered if item.get("expected_roi") is not None]
        realized_values = [_safe_float(item.get("realized_revenue")) for item in filtered if item.get("realized_revenue") is not None]
        positives = sum(1 for item in filtered if _safe_bool(item.get("verified")) and _safe_float(item.get("realized_revenue")) > 0.0)
        sample_count = len(filtered)

        avg_expected_roi = sum(expected_roi_values) / len(expected_roi_values) if expected_roi_values else 0.0
        avg_realized_revenue = sum(realized_values) / len(realized_values) if realized_values else 0.0
        positive_roi_rate = positives / verified_samples if verified_samples > 0 else 0.0
        confidence_hint = min(1.0, (verified_samples / 5.0) * 0.7 + positive_roi_rate * 0.3)

        return ChannelROISnapshot(
            channel=channel or "default",
            action_type=action_type or "unknown",
            verified_samples=verified_samples,
            unverified_samples=unverified_samples,
            average_expected_roi=avg_expected_roi,
            average_realized_revenue=avg_realized_revenue,
            positive_roi_rate=positive_roi_rate,
            confidence_hint=confidence_hint,
            metadata={
                "owner": "execution.channel_roi_memory",
                "sample_count": sample_count,
            },
        )

    def from_world_state(self, *, world_state: Any | None, channel: str, action_type: str) -> ChannelROISnapshot:
        state = _safe_dict(world_state)
        meta = _safe_dict(state.get("meta"))
        roi_history = meta.get("economic_roi_history")
        records = list(roi_history) if isinstance(roi_history, (list, tuple)) else []
        if not records:
            direct = meta.get("economic_feedback_history")
            records = list(direct) if isinstance(direct, (list, tuple)) else []
        if not records:
            closed_loop = _safe_dict(meta.get("execution_closed_loop"))
            history = list(closed_loop.get("execution_history") or [])
            for item in history:
                feedback = _safe_dict(item).get("economic_feedback")
                if isinstance(feedback, Mapping):
                    records.append(dict(feedback))
        return self.from_records(channel=channel, action_type=action_type, records=records)


__all__ = ["CANON_CHANNEL_ROI_MEMORY", "ChannelROIMemory", "ChannelROISnapshot"]
