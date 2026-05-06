from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping
CANON_ROUTE_CONTINUITY_MEMORY = True
def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}
@dataclass(frozen=True)
class RouteContinuitySignal:
    route_key: str
    success_streak: int = 0
    verified_success_streak: int = 0
    stability_score: float = 0.0
    route_confidence_peak: float = 0.0
    last_focus_mode: str = ''
    def advisory_bonus(self) -> float:
        streak_bonus = min(0.08, 0.015 * float(max(self.success_streak, 0)))
        verified_bonus = min(0.08, 0.020 * float(max(self.verified_success_streak, 0)))
        stability_bonus = min(0.06, max(0.0, min(1.0, float(self.stability_score))) * 0.06)
        confidence_bonus = min(0.05, max(0.0, min(1.0, float(self.route_confidence_peak))) * 0.05)
        return streak_bonus + verified_bonus + stability_bonus + confidence_bonus
    def to_dict(self) -> dict[str, Any]:
        return {
            'route_key': self.route_key,
            'success_streak': int(self.success_streak),
            'verified_success_streak': int(self.verified_success_streak),
            'stability_score': float(self.stability_score),
            'route_confidence_peak': float(self.route_confidence_peak),
            'last_focus_mode': self.last_focus_mode,
            'advisory_bonus': self.advisory_bonus(),
        }
class RouteContinuityMemory:
    def read(self, *, route_key: str, runtime_info: Mapping[str, Any] | None = None) -> RouteContinuitySignal:
        runtime_payload = _safe_dict(runtime_info)
        continuity = _safe_dict(runtime_payload.get('continuity_memory'))
        if not continuity:
            continuity = _safe_dict(runtime_payload.get('route_memory'))
        return RouteContinuitySignal(
            route_key=route_key,
            success_streak=int(continuity.get('success_streak') or 0),
            verified_success_streak=int(continuity.get('verified_success_streak') or 0),
            stability_score=max(0.0, min(1.0, float(continuity.get('stability_score') or 0.0))),
            route_confidence_peak=max(0.0, min(1.0, float(continuity.get('route_confidence_peak') or 0.0))),
            last_focus_mode=str(continuity.get('last_focus_mode') or '').strip(),
        )
