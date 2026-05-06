from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CRITICAL = [
    ROOT / "runtime/guard.py",
    ROOT / "runtime/executor.py",
    ROOT / "runtime/handlers/ads_apply_execute.py",
    ROOT / "runtime/platform/event_store/postgres_event_store.py",
]


def test_no_silent_passes_in_critical_files():
    offenders = []
    needles = ["except Exception:\n            pass", "except:\n            pass"]
    for path in CRITICAL:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(n in text for n in needles):
            offenders.append(str(path))
    assert offenders == []
