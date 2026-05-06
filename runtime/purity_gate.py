from runtime.decision import DecisionEnvelope


class PurityGate:
    """
    НЕ рантайм.
    НЕ executor.
    Только формальная проверка корректности решения.
    """

    def validate(self, envelope: DecisionEnvelope) -> None:
        envelope.verify()
