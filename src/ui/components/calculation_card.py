from nicegui import ui

from src.application.calculation_service import CalculationService
from src.application.source_service import SourceService
from src.domain.calculation import Calculation
from src.ui.components.util import setter


def calculation_card(
    code: str,
    calc: Calculation,
    sources: SourceService,
    calculations: CalculationService,
    on_change,
    remove,
) -> None:
    all_sources = sources.list_all(code)
    by_id = {s.id: s for s in all_sources}
    formulas = calculations.formulas()
    last = {'evaluation': calculations.evaluate(code, calc)}

    def variables_of(source_id: str) -> dict[str, str]:
        source = by_id.get(source_id)
        if source is None:
            return {}
        try:
            return sources.numeric_variables(code, source)
        except (OSError, ValueError):
            return {}

    def update_result() -> None:
        last['evaluation'] = calculations.evaluate(code, calc)
        result.refresh()
        on_change()

    def change_formula(event) -> None:
        old, new = formulas.get(calc.formula_id), formulas.get(event.value)
        if old is not None and new is not None and calc.name == old.name:
            calc.name = new.name  # o nome só acompanha se o usuário não tinha mudado
        calc.formula_id = event.value
        calc.inputs = {}
        calc.parameters = {}
        controls.refresh()
        update_result()

    def change_source(event) -> None:
        calc.source_id = event.value
        options = variables_of(calc.source_id)
        calc.inputs = {a: c for a, c in calc.inputs.items() if c in options}
        controls.refresh()
        update_result()

    def change_input(argument: str):
        def handler(event) -> None:
            calc.inputs[argument] = event.value
            update_result()

        return handler

    def change_parameter(name: str):
        def handler(event) -> None:
            if event.value is None:
                calc.parameters.pop(name, None)  # campo vazio: volta ao padrão
            else:
                calc.parameters[name] = event.value
            update_result()

        return handler

    @ui.refreshable
    def controls() -> None:
        formula = formulas.get(calc.formula_id)
        source = by_id.get(calc.source_id)
        options = variables_of(calc.source_id)

        formula_options = {fid: f.name for fid, f in formulas.items()}
        if calc.formula_id not in formula_options:
            formula_options[calc.formula_id] = f'{calc.formula_name or calc.formula_id} (não instalada)'
        source_options = {s.id: f'{s.id} · {s.origin}' for s in all_sources}
        if calc.source_id not in source_options:
            source_options[calc.source_id] = f'{calc.source_id} (indisponível)'

        with ui.row().classes('w-full items-end'):
            ui.select(
                formula_options, label='Fórmula', value=calc.formula_id, on_change=change_formula
            ).props('outlined dense').classes('w-72')
            ui.select(
                source_options, label='Fonte', value=calc.source_id, on_change=change_source
            ).props('outlined dense').classes('w-64')

        if formula is None:
            return
        if formula.description:
            ui.label(formula.description).classes('text-gray-400')
        with ui.row().classes('w-full items-end'):
            for argument, description in formula.inputs.items():
                current = calc.inputs.get(argument)
                input_options = dict(options)
                if current and current not in input_options:
                    input_options[current] = f'{current} (indisponível)'
                ui.select(
                    input_options, label=description, value=current, on_change=change_input(argument)
                ).props('outlined dense').classes('w-64')
        if formula.parameters:
            with ui.row().classes('w-full items-end'):
                for name, info in formula.parameters.items():
                    value = calc.parameters.get(name)
                    ui.number(
                        info.description,
                        value=info.default if value is None else value,
                        on_change=change_parameter(name),
                    ).props('outlined dense debounce=300').classes('w-64')
        if formula.uses_time and source is not None and not source.sample_rate_hz:
            ui.label(
                'Esta fórmula usa o tempo: informe a taxa de amostragem desta fonte, no Log.'
            ).classes('text-orange-400')

    @ui.refreshable
    def result() -> None:
        evaluation = last['evaluation']
        with ui.card().classes('w-full').props('flat bordered'):
            if not evaluation.installed:
                ui.label(f'A fórmula "{calc.formula_id}" não está instalada neste computador.').classes(
                    'text-orange-400'
                )
                if calc.result is not None:
                    ui.label(
                        f'Último resultado salvo: {calc.result:.6g} {calc.unit} '
                        f'(fórmula "{calc.formula_name}")'
                    )
            elif evaluation.error:
                ui.label(evaluation.error).classes('text-orange-400')
            else:
                ui.label(f'{evaluation.value:.6g} {calc.unit}'.strip()).classes('text-3xl font-bold')

    with ui.card().classes('w-full'):
        with ui.row().classes('w-full items-center justify-between'):
            ui.input(
                'Nome do cálculo', value=calc.name, on_change=setter(calc, 'name', on_change)
            ).bind_value_from(calc, 'name').props('outlined dense debounce=500').classes('grow')
            ui.button('Remover cálculo', icon='delete', on_click=lambda: remove(calc)).props(
                'flat color=negative'
            )
        controls()
        result()
        ui.textarea(
            'Observações', value=calc.notes, on_change=setter(calc, 'notes', on_change)
        ).props('outlined autogrow debounce=500').classes('w-full')