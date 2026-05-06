from __future__ import annotations


class ShadowEvaluator:
    """
    Проверяет candidate policy на исторических данных ДО canary.

    Важно: чтобы не нарушать "Decision Sovereignty" инварианты и
    AST-запреты на .optimize(...) вызовы вне фасада, этот модуль
    НЕ вызывает policy.optimize(...).

    Ожидается, что policy:
      - либо является callable: policy(state) -> action
      - либо имеет метод predict(state) / act(state) / select(state)
    """

    def evaluate(self, dataset, policy) -> float:
        errors = 0
        total = 0
        fn = None
        if callable(policy):
            fn = policy
        else:
            for name in ("predict", "act", "select"):
                cand = getattr(policy, name, None)
                if callable(cand):
                    fn = cand
                    break
        if fn is None:
            return 1.0
        for state, expected in dataset:
            decision = fn(state)
            if decision != expected:
                errors += 1
            total += 1
        return errors / total if total else 1.0
