from __future__ import annotations

import math

CANON_RUNTIME_SUPPORT_SAFETY_RUNTIME_PACKAGE_OWNER = True
CANON_COMPAT_SHIM = True

def detect_numeric_anomaly(value: float, threshold: float) -> bool:
    if math.isnan(value) or math.isinf(value):
        return True
    return abs(value) > threshold

class CollapseDetector:
    def collapsed(self, entropy: float, min_entropy: float = 1e-6) -> bool:
        return entropy < min_entropy

class DegradedModeEntry:
    def enter(self) -> dict[str, bool]:
        return {"degraded": True}

def detect_drift(baseline: float, current: float, threshold: float = 0.1) -> bool:
    return abs(current - baseline) > threshold

class EmergencyStop:
    def trigger(self, reason: str) -> dict[str, str]:
        return {"stopped": "true", "reason": reason}

class HumanOverride:
    def required(self, risk_level: str) -> bool:
        return risk_level in {"high", "critical"}

class RewardHackingDetector:
    def detected(
        self,
        reward_gain: float,
        business_gain: float,
        max_gap: float = 0.2,
    ) -> bool:
        return (reward_gain - business_gain) > max_gap

class RunawayFeedbackFirewall:
    def blocked(self, loop_gain: float, max_gain: float = 1.0) -> bool:
        return loop_gain > max_gain

class SafeShutdown:
    def execute(self) -> dict[str, bool]:
        return {"shutdown": True}

class SelfReinforcementFirewall:
    def blocked(self, self_reference_ratio: float, max_ratio: float = 0.5) -> bool:
        return self_reference_ratio > max_ratio

__all__ = [
    "detect_numeric_anomaly",
    "CollapseDetector",
    "DegradedModeEntry",
    "detect_drift",
    "EmergencyStop",
    "HumanOverride",
    "RewardHackingDetector",
    "RunawayFeedbackFirewall",
    "SafeShutdown",
    "SelfReinforcementFirewall",
]
