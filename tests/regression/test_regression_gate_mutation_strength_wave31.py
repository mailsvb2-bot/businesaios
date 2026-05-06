from formal.regression_gate import evaluate_mutation_strength, replay_cases_from_corpus, replay_runtime_decision


def test_mutation_strength_kills_expected_contract_and_trace_mutants_wave31() -> None:
    report = evaluate_mutation_strength(replay_cases_from_corpus(), replay_runtime_decision)
    assert report["total"] >= 3
    assert report["ok"], report["results"]
    assert report["mutation_score"] == 1.0
