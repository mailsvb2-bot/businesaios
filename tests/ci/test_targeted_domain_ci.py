from __future__ import annotations

from scripts.ci.targeted_domain_ci import touched_domains


def test_core_payment_roots_are_billing_domain() -> None:
    changed = [
        "core/payments/yookassa_webhook.py",
        "core/economics/brain.py",
        "core/billing/invoice_projection.py",
    ]

    assert touched_domains(changed) == ["billing"]


def test_unknown_core_paths_do_not_trigger_billing_domain() -> None:
    assert touched_domains(["core/unrelated/module.py"]) == []



def test_capability_and_autonomy_roots_trigger_targeted_domain() -> None:
    changed = [
        "application/business_autonomy/integration_capability_catalog.py",
        "application/autonomy/autonomy_state_assembly.py",
        "runtime/business_autonomy/provider_live_probe_runtime.py",
    ]

    assert touched_domains(changed) == ["capability_autonomy"]


def test_targeted_ci_runs_every_selected_file_in_bounded_chunks(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from scripts.ci import step_targeted_domain_tests as step

    selected = [f"tests/test_provider_{index:02d}.py" for index in range(25)]
    chunks = []
    monkeypatch.delenv("TARGETED_DOMAIN_CHUNK_SIZE", raising=False)
    monkeypatch.setattr(step.targeted, "changed_files", lambda _base: [])
    monkeypatch.setattr(step.targeted, "touched_domains", lambda _changed: ["provider"])
    monkeypatch.setattr(step.targeted, "matching_tests", lambda _domains: selected)
    monkeypatch.setattr(step, "junit_dir", lambda: tmp_path)
    monkeypatch.setattr(step, "_write_summary_junit", lambda **_kwargs: None)
    monkeypatch.setattr(step, "_write_coverage_honesty_artifact", lambda **_kwargs: None)

    def run_pytest(args, *, timeout):
        assert timeout == 300
        filenames = [arg for arg in args if arg in selected]
        chunks.append(filenames)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(step, "run_pytest", run_pytest)
    ok, message = step.run()
    assert ok is True
    assert [len(chunk) for chunk in chunks] == [6, 6, 6, 6, 1]
    assert [path for chunk in chunks for path in chunk] == selected
    assert "collected_chunks=5" in message
