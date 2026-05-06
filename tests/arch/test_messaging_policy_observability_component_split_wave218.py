from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FASTAPI_COMPONENTS=(
    "runtime/boot/web/fastapi_components/navigation.py",
    "runtime/boot/web/fastapi_components/snapshot.py",
    "runtime/boot/web/fastapi_components/traces.py",
    "runtime/boot/web/fastapi_components/dashboard.py",
    "runtime/boot/web/fastapi_components/alerts.py",
    "runtime/boot/web/fastapi_components/alert_subscriptions.py",
    "runtime/boot/web/fastapi_components/messaging_preferences.py",
)
FLASK_COMPONENTS=(
    "runtime/boot/web/flask_components/navigation.py",
    "runtime/boot/web/flask_components/snapshot.py",
    "runtime/boot/web/flask_components/traces.py",
    "runtime/boot/web/flask_components/dashboard.py",
    "runtime/boot/web/flask_components/alerts.py",
    "runtime/boot/web/flask_components/alert_subscriptions.py",
    "runtime/boot/web/flask_components/messaging_preferences.py",
)

def test_all_component_boot_files_exist() -> None:
    missing=[]
    for rel in FASTAPI_COMPONENTS + FLASK_COMPONENTS:
        if not (ROOT/rel).exists():
            missing.append(rel)
    assert not missing, missing

def test_component_boot_files_are_thin() -> None:
    offenders=[]
    for rel in FASTAPI_COMPONENTS + FLASK_COMPONENTS:
        text=(ROOT/rel).read_text(encoding="utf-8")
        if text.count("\n") > 30:
            offenders.append(rel)
    assert not offenders, offenders
