from formal.regression_gate import (
    evaluate_mutation_strength,
    load_trace_corpus,
    replay_cases_from_corpus,
    replay_runtime_decision,
    run_replay_suite,
    summarize_corpus,
)


def test_replay_harness_matches_runtime_trace_corpus_wave31() -> None:
    suite = run_replay_suite(replay_cases_from_corpus(), replay_runtime_decision)
    assert suite["checked_cases"] >= 3
    assert suite["ok"], suite["failing_cases"]


def test_mutation_strength_kills_expected_contract_and_trace_mutants_wave31() -> None:
    report = evaluate_mutation_strength(replay_cases_from_corpus(), replay_runtime_decision)
    assert report["total"] >= 3
    assert report["ok"], report["results"]
    assert report["mutation_score"] == 1.0


def test_trace_corpus_is_present_and_named_wave31() -> None:
    summary = summarize_corpus()
    assert summary["ok"]
    assert summary["count"] >= 3
    names = set(summary["names"])
    assert {"runtime_path_executed", "runtime_path_blocked", "runtime_path_execute_once"}.issubset(names)


def test_trace_corpus_entries_are_contract_complete_wave31() -> None:
    entries = load_trace_corpus()
    for entry in entries:
        assert "status" in entry.expected_contract
        assert "action_type" in entry.expected_contract
        assert "trace" in entry.expected_contract
        assert entry.expected_trace["route"] == "DecisionCore->RuntimeExecutor"
