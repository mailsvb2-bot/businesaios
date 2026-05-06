from formal.regression_gate import replay_runtime_decision, replay_cases_from_corpus, run_replay_suite


def test_replay_harness_matches_runtime_trace_corpus_wave31() -> None:
    suite = run_replay_suite(replay_cases_from_corpus(), replay_runtime_decision)
    assert suite["checked_cases"] >= 3
    assert suite["ok"], suite["failing_cases"]
