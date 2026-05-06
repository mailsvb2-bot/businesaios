from orchestration.signal_pipeline import SignalPipeline


def test_signal_pipeline_preserves_signal_count():
    pipeline = SignalPipeline()
    signals = [{'score': 1}, {'score': 0}]
    assert len(pipeline.run(signals)) == 2
