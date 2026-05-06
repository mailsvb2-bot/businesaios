def test_ring_closed_imports():
    """Guarantee DecisionCore remains the only decide() definition."""
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]

    bad = []
    for py in root.rglob("*.py"):
        if "decision_core.py" in str(py):
            continue

        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "decide":
                bad.append(str(py))

    assert not bad, "Forbidden decide() outside DecisionCore:\n" + "\n".join(bad)