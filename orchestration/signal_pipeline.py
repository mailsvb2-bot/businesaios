class SignalPipeline:
    def run(self, signals: list[dict]) -> list[dict]:
        return [dict(signal) for signal in signals]
