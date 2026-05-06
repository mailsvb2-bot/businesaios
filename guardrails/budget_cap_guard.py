class BudgetCapGuard:
    def __init__(self, cap: float = 2000.0) -> None:
        self.cap = cap

    def check(self, payload: dict) -> tuple[bool, str]:
        amount = float(payload.get('amount', 0.0))
        return (amount <= self.cap, 'budget_cap_exceeded' if amount > self.cap else 'ok')
