from pathlib import Path


def test_calculator_is_reachable_from_product_shell() -> None:
    main = Path('frontend/src/main.jsx').read_text(encoding='utf-8')
    assert 'AcquisitionCalculatorPage' in main
    assert 'CalculatorLauncher' in main
    assert '=== "/calculator"' in main
    assert '<App /><CalculatorLauncher />' in main


def test_calculator_calls_canonical_public_endpoint_and_labels_assumptions() -> None:
    source = Path('frontend/src/AcquisitionCalculatorPage.jsx').read_text(encoding='utf-8')
    assert '/public-site/acquisition/feasibility' in source
    assert 'scenario_source' not in source
    assert 'Это сценарный расчёт, а не подтверждённые метрики вашего бизнеса.' in source
    assert 'Никаких денег и рекламных действий калькулятор не запускает.' in source
    assert 'conversion_rate:' in source and 'avg_stage_days:' in source
    assert 'Подключить BusinessAIOS' in source


def test_calculator_surfaces_business_outcomes_not_raw_diagnostics() -> None:
    source = Path('frontend/src/AcquisitionCalculatorPage.jsx').read_text(encoding='utf-8')
    for label in ('Достижимо клиентов', 'Нужно бюджета', 'Рекомендуемый бюджет/день', 'Расчётный CAC', 'LTV / CAC'):
        assert label in source
    assert 'JSON.stringify(result' not in source
    css = Path('frontend/src/acquisition-calculator.css').read_text(encoding='utf-8')
    assert '@media(max-width:850px)' in css
    assert '.calculator-launcher' in css
