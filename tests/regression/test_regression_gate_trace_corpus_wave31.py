from formal.regression_gate import load_trace_corpus, summarize_corpus


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
