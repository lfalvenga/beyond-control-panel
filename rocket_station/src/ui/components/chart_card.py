from nicegui import ui

from src.application.report_service import ReportService
from src.application.source_service import SourceService
from src.domain.enums import Axis
from src.domain.report import PALETTE, Chart, Series
from src.ui.components.echarts import chart_options
from src.ui.components.util import setter

AXIS_LABELS = {Axis.LEFT: 'Eixo esquerdo', Axis.RIGHT: 'Eixo direito'}


def chart_card(
    code: str,
    chart: Chart,
    sources: SourceService,
    report: ReportService,
    on_change,
    remove,
) -> None:
    all_sources = sources.list_all(code)
    by_id = {s.id: s for s in all_sources}

    def variables():
        source = by_id.get(chart.source_id)
        if source is None:
            return None, {}
        try:
            return source, sources.numeric_variables(code, source)
        except (OSError, ValueError):
            return source, {}

    def draw() -> None:
        area.clear()
        with area:
            data = report.chart_data(code, chart)
            if data.message:
                ui.label(data.message).classes('text-gray-400')
                return
            ui.echart(chart_options(chart.title, data)).classes('w-full').style('height: 440px')

    def changed() -> None:
        on_change()
        draw()

    def change_source(event) -> None:
        chart.source_id = event.value
        source, options = variables()
        chart.series = [s for s in chart.series if s.column in options]  # aproveita as que existem
        time_ok = chart.x == 'time' and source is not None and bool(source.sample_rate_hz)
        if chart.x != 'sample' and chart.x not in options and not time_ok:
            chart.x = 'sample'
        controls.refresh()
        changed()

    def add_series() -> None:
        _, options = variables()
        if not options:
            ui.notify('Esta fonte não tem colunas numéricas.', type='warning')
            return
        used = {s.column for s in chart.series}
        free = next((c for c in options if c not in used), next(iter(options)))
        chart.series.append(Series(free, Axis.LEFT, PALETTE[len(chart.series) % len(PALETTE)]))
        controls.refresh()
        changed()

    def remove_series(series: Series) -> None:
        chart.series.remove(series)
        controls.refresh()
        changed()

    @ui.refreshable
    def controls() -> None:
        source, options = variables()
        source_options = {s.id: f'{s.id} · {s.origin}' for s in all_sources}
        if chart.source_id not in source_options:
            source_options[chart.source_id] = f'{chart.source_id} (indisponível)'
        x_options = {'sample': 'Amostra'}
        if source is not None and source.sample_rate_hz:
            x_options['time'] = 'Tempo (s)'  # só existe se a fonte tiver taxa
        x_options.update(options)
        if chart.x not in x_options:
            x_options[chart.x] = f'{chart.x} (indisponível)'

        with ui.row().classes('w-full items-end'):
            ui.select(
                source_options, label='Fonte', value=chart.source_id, on_change=change_source
            ).props('outlined dense').classes('w-64')
            ui.select(
                x_options, label='Eixo X', value=chart.x, on_change=setter(chart, 'x', changed)
            ).props('outlined dense').classes('w-64')
            ui.button('Adicionar variável', icon='add', on_click=add_series).props('outline')

        for series in chart.series:
            y_options = dict(options)
            if series.column not in y_options:
                y_options[series.column] = f'{series.column} (indisponível)'
            with ui.row().classes('w-full items-center'):
                ui.select(
                    y_options, label='Variável', value=series.column,
                    on_change=setter(series, 'column', changed),
                ).props('outlined dense').classes('w-64')
                ui.select(
                    AXIS_LABELS, label='Eixo', value=series.axis,
                    on_change=setter(series, 'axis', changed),
                ).props('outlined dense').classes('w-48')
                ui.color_input(
                    'Cor', value=series.color, preview=True,
                    on_change=setter(series, 'color', changed),
                ).classes('w-40')
                ui.button(icon='close', on_click=lambda s=series: remove_series(s)).props(
                    'flat round dense'
                )

    with ui.card().classes('w-full'):
        with ui.row().classes('w-full items-center justify-between'):
            ui.input(
                'Título', value=chart.title, on_change=setter(chart, 'title', lambda: changed())
            ).props('outlined dense debounce=500').classes('grow')
            ui.button('Remover gráfico', icon='delete', on_click=lambda: remove(chart)).props(
                'flat color=negative'
            )
        controls()
        area = ui.column().classes('w-full')
        draw()
        ui.textarea(
            'Observações', value=chart.notes, on_change=setter(chart, 'notes', on_change)
        ).props('outlined autogrow debounce=500').classes('w-full')