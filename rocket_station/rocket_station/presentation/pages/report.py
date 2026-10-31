from dataclasses import asdict

from nicegui import ui

from rocket_station.application.calculation_service import CalculationService
from rocket_station.application.report_service import ReportService
from rocket_station.application.source_service import SourceService
from rocket_station.domain.errors import ValidationError
from rocket_station.domain.report import Report
from rocket_station.presentation.components.calculation_card import calculation_card
from rocket_station.presentation.components.chart_card import chart_card
from rocket_station.application.operation_service import OperationService
from rocket_station.presentation.components.operation_page import operation_page

_drafts: dict[str, Report] = {}


def _content(
    code: str,
    operation_id: str,
    reports: ReportService,
    sources: SourceService,
    calculations: CalculationService,
) -> None:
    key = operation_id or code  # o rascunho pertence à operação (id), não ao código
    try:
        has_sources = bool(sources.list_all(code))
    except (OSError, ValueError, KeyError, TypeError):
        ui.label('Não foi possível ler as fontes de dados desta operação.').classes('text-red-400')
        return
    if not has_sources:
        ui.label('Importe um CSV do SD na tela Log para montar gráficos e cálculos.').classes(
            'text-gray-400'
        )
        return

    if key in _drafts:
        report = _drafts[key]  # volta ao que estava sendo editado, salvo ou não
    else:
        try:
            report = reports.load(code)
        except (OSError, ValueError, KeyError, TypeError):
            ui.notify('O arquivo do relatório está ilegível; começando do zero.', type='warning')
            report = Report()
        _drafts[key] = report

    def from_disk() -> Report:
        try:
            return reports.load(code)
        except (OSError, ValueError, KeyError, TypeError):
            return Report()

    def update_state() -> None:
        dirty = asdict(report) != asdict(from_disk())
        notice.set_visibility(dirty)
        discard_button.set_visibility(dirty)
        save_button.set_enabled(dirty)

    def save() -> None:
        try:
            reports.save(code, report)
        except (OSError, ValueError) as error:
            ui.notify(f'Não foi possível salvar o relatório: {error}', type='negative')
            return
        update_state()
        ui.notify('Relatório salvo.', type='positive')

    def discard() -> None:
        discard_dialog.close()
        disk = from_disk()
        report.charts[:] = disk.charts  # troca o conteúdo das mesmas listas
        report.calculations[:] = disk.calculations
        charts_list.refresh()
        calculations_list.refresh()
        update_state()
        ui.notify('Alterações descartadas.', type='info')

    def remove_chart(chart) -> None:
        report.charts.remove(chart)
        charts_list.refresh()
        update_state()

    def add_chart() -> None:
        try:
            report.charts.append(reports.new_chart(code))
        except ValidationError as error:
            ui.notify(str(error), type='warning')
            return
        charts_list.refresh()
        update_state()

    def remove_calculation(calculation) -> None:
        report.calculations.remove(calculation)
        calculations_list.refresh()
        update_state()

    def add_calculation() -> None:
        try:
            report.calculations.append(calculations.new(code))
        except ValidationError as error:
            ui.notify(str(error), type='warning')
            return
        calculations_list.refresh()
        update_state()

    @ui.refreshable
    def charts_list() -> None:
        if not report.charts:
            ui.label('Nenhum gráfico ainda. Clique em "Adicionar gráfico".').classes('text-gray-400')
        for chart in report.charts:
            chart_card(code, chart, sources, reports, update_state, remove_chart)

    @ui.refreshable
    def calculations_list() -> None:
        if not report.calculations:
            ui.label('Nenhum cálculo ainda. Clique em "Adicionar cálculo".').classes('text-gray-400')
        for calculation in report.calculations:
            calculation_card(
                code, calculation, sources, calculations, update_state, remove_calculation
            )

    discard_dialog = ui.dialog()
    with discard_dialog, ui.card():
        ui.label('Descartar alterações?').classes('text-lg font-bold')
        ui.label('O relatório volta ao último estado salvo. O que você mudou desde então será perdido.')
        with ui.row().classes('justify-end w-full'):
            ui.button('Cancelar', on_click=discard_dialog.close).props('flat')
            ui.button('Descartar', on_click=discard, color='negative')

    with ui.row().classes('w-full items-center justify-end'):
        notice = ui.label('Alterações não salvas').classes('text-orange-400')
        discard_button = ui.button('Descartar alterações', on_click=discard_dialog.open).props('flat')
        save_button = ui.button('Salvar relatório', icon='save', on_click=save)

    with ui.row().classes('w-full items-center justify-between'):
        ui.label('Gráficos').classes('text-2xl font-bold')
        ui.button('Adicionar gráfico', icon='add_chart', on_click=add_chart).props('outline')
    charts_list()

    ui.separator()

    with ui.row().classes('w-full items-center justify-between'):
        ui.label('Cálculos').classes('text-2xl font-bold')
        ui.button('Adicionar cálculo', icon='calculate', on_click=add_calculation).props('outline')
    for file, reason in calculations.load_errors().items():
        ui.label(f'A fórmula "{file}" não pôde ser carregada: {reason}').classes('text-orange-400')
    if not calculations.formulas():
        ui.label(
            'Nenhuma fórmula encontrada na pasta formulas/. Veja formulas/_modelo.py para criar a primeira.'
        ).classes('text-gray-400')
    calculations_list()

    update_state()


def build(
    operations: OperationService,
    reports: ReportService,
    sources: SourceService,
    calculations: CalculationService,
    session: SessionState,
) -> None:
    operation_page(
        'Relatório',
        operations,
        session,
        lambda op: _content(op.code, op.id, reports, sources, calculations),
        react_to_data=True,
    )