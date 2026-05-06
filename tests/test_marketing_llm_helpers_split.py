from pathlib import Path


def test_marketing_llm_composer_reduced_and_helperized():
    composer = Path("core/marketing/llm_composer.py").read_text(encoding="utf-8")
    assert "validate_marketing_text" in composer
    assert "emit_trace_async" in composer
    assert len(composer.splitlines()) < 520
