from ml.common.score_output import ScoreOutput


class ScoreReasoning:
    def explain(self, output: ScoreOutput) -> dict:
        return {
            'kind': 'score_reasoning',
            'score': output.bounded_score(),
            'confidence': output.bounded_confidence(),
            'reasons': list(output.reasons),
        }
