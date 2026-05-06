from config.system_config import OptimizationObjective
from core.constraints.decision import DecisionConstraints


def test_shared_optimization_objective_is_profit_adjusted_growth():
    assert OptimizationObjective().name == 'profit_adjusted_growth'
    assert DecisionConstraints().objective_name == 'profit_adjusted_growth'
