FORBIDDEN_DECISION_CLASS_NAMES = {
    'StrategyBrain',
    'GrowthBrain',
    'AutonomousBrain',
    'SecondDecisionCore',
    'DecisionEngineFacade',
}
FORBIDDEN_DECISION_METHODS = {'decide_strategy', 'issue_strategy', 'emit_final_action', 'select_final_action'}
