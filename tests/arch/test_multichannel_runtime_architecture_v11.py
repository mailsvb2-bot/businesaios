from pathlib import Path

FORBIDDEN = [
    "decide_price(",
    "select_growth_strategy(",
    "issue_decision(",
    "autonomous_campaign(",
    "decisioncore",
    "pricing",
    "growth",
    "ltv",
    "marketing strategy",
    "world model",
]

REQUIRED = [
    "interfaces/messaging_runtime/bootstrap.py",
    "interfaces/messaging_runtime/pipeline.py",
    "interfaces/messaging_runtime/outbound/delivery_dispatcher.py",
    "interfaces/messaging_runtime/contracts.py",
]


def test_required_singletons_exist():
    for path in REQUIRED:
        assert Path(path).exists(), path


def test_no_parallel_bootstrap_or_pipeline_variants():
    root = Path("interfaces/messaging_runtime")
    bootstrap_like = [p for p in root.rglob("*.py") if "bootstrap" in p.name.lower()]
    pipeline_like = [p for p in root.rglob("*.py") if "pipeline" in p.name.lower()]
    dispatcher_like = [p for p in root.rglob("*.py") if "dispatcher" in p.name.lower()]
    assert len(bootstrap_like) == 1
    assert len(pipeline_like) == 1
    assert len(dispatcher_like) == 1


def test_runtime_layer_has_no_business_decision_brain():
    root = Path("interfaces/messaging_runtime")
    contents = []
    for path in root.rglob("*.py"):
        contents.append(path.read_text(encoding="utf-8").lower())
    joined = "\n".join(contents)
    for forbidden in FORBIDDEN:
        assert forbidden not in joined
