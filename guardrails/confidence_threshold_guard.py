class ConfidenceThresholdGuard:
    def __init__(self, threshold: float = 0.60) -> None:
        self.threshold = threshold

    def check(self, payload: dict) -> tuple[bool, str]:
        value = float(payload.get('confidence', 0.0))
        return (value >= self.threshold, 'confidence_below_threshold' if value < self.threshold else 'ok')
