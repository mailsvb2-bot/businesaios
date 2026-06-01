from core.llm.guardrails import enforce_single_message, forbid_phrases, require_max_chars


def test_enforce_single_message():
    t = "Hello\n\nWorld  \n"
    r = enforce_single_message(t)
    assert r.ok
    assert r.fixed_text == "Hello World"


def test_forbid_phrases():
    r = forbid_phrases("I use DecisionCore", ["DecisionCore"])
    assert not r.ok


def test_require_max_chars():
    r = require_max_chars("a" * 10, 5)
    assert r.ok
    assert r.fixed_text.endswith("…")
