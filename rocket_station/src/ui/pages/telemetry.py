import time
from dataclasses import asdict

from nicegui import ui

from src.ui.state.session import SessionState
from src.application.recording_service import RecordingService
from src.application.telemetry_config_service import TelemetryConfigService
from src.application.telemetry_service import TelemetryService
from src.config import SILENCE_YELLOW_S
from src.domain.enums import Axis
from src.domain.errors import ValidationError
from src.domain.report import PALETTE, Series
from src.domain.telemetry import (
    X_PACKET,
    X_TIME,
    ExpectedVariable,
    LiveChart,
    TelemetryConfig,
)
from src.ui.components.chart_card import AXIS_LABELS
from src.ui.components.echarts import AXIS, TEXT, TITLE, y_axis
from src.ui.components.util import setter
from src.ui.theme import GRAY, GREEN, RED, YELLOW
from src.application.operation_service import OperationService
from src.ui.components.operation_page import operation_page

# rascunho da configuração por operação (id), ainda não salvo no pacote
_drafts: dict[str, TelemetryConfig] = {}

WINDOW_OPTIONS = {
    'all': 'Tudo',
    '10': 'Últimos 10 s',
    '30': 'Últimos 30 s',
    '60': 'Últimos 60 s',
    '120': 'Últimos 2 min',
    '300': 'Últimos 5 min',
}


def _variable_options(config: TelemetryConfig, telemetry: TelemetryService) -> dict[str, str]:
    options = {e.name: config.label(e.name) for e in config.expected if e.name}
    for variable in telemetry.variables.values():
        if variable.numeric and variable.name not in options:
            options[variable.name] = variable.name
    return options


def _live_options(chart: LiveChart, config: TelemetryConfig) -> dict:
    names_by_axis = {Axis.LEFT: [], Axis.RIGHT: []}
    for s in chart.series:
        names_by_axis[s.axis].append(config.label(s.column))
    axes = [a for a in (Axis.LEFT, Axis.RIGHT) if names_by_axis[a]] or [Axis.LEFT]
    index = {a: i for i, a in enumerate(axes)}
    x_name = {X_TIME: 'Tempo (s)', X_PACKET: 'Número do pacote'}.get(chart.x, config.label(chart.x))
    return {
        'animation': False,  # gráfico ao vivo: sem animação a cada atualização
        'title': {'text': chart.title, 'left': 'center', 'textStyle': {'color': TITLE}},
        'tooltip': {'trigger': 'axis'},
        'legend': {'top': 30, 'textStyle': {'color': TEXT}},
        'grid': {'left': 70, 'right': 70 if len(axes) == 2 else 30, 'top': 80, 'bottom': 60},
        'xAxis': {
            'type': 'value',
            'name': x_name,
            'nameLocation': 'middle',
            'nameGap': 30,
            'scale': True,
            'nameTextStyle': {'color': TEXT},
            'axisLabel': {'color': TEXT},
            'axisLine': {'lineStyle': {'color': AXIS}},
            'splitLine': {'show': False},
        },
        'yAxis': [
            y_axis(' / '.join(names_by_axis[a]), 'left' if a is Axis.LEFT else 'right', a is axes[0])
            for a in axes
        ],
        'series': [
            {
                'name': config.label(s.column),
                'type': 'line',
                'yAxisIndex': index[s.axis],
                'showSymbol': False,
                'lineStyle': {'color': s.color, 'width': 2},
                'itemStyle': {'color': s.color},
                'data': [],  # preenchido pelo temporizador
            }
            for s in chart.series
        ],
    }


def _live_card(chart, config, telemetry, on_change, remove, updaters: list, option_refreshers: list) -> None:
    ref = {}

    def update_data() -> None:
        graph = ref.get('graph')
        if graph is None:
            return
        for i, s in enumerate(chart.series):
            graph.options['series'][i]['data'] = telemetry.history.points(
                s.column, chart.x, chart.window_s
            )
        graph.update()

    def draw() -> None:
        area.clear()
        with area:
            ref['graph'] = ui.echart(_live_options(chart, config)).classes('w-full').style('height: 360px')
        update_data()

    def changed() -> None:
        on_change()
        draw()

    def window_changed(event) -> None:
        chart.window_s = None if event.value == 'all' else float(event.value)
        on_change()
        update_data()

    def add_series() -> None:
        options = _variable_options(config, telemetry)
        if not options:
            ui.notify('Declare uma variável esperada (ou conecte a estação) primeiro.', type='warning')
            return
        used = {s.column for s in chart.series}
        free = next((n for n in options if n not in used), next(iter(options)))
        chart.series.append(Series(free, Axis.LEFT, PALETTE[len(chart.series) % len(PALETTE)]))
        controls.refresh()
        changed()

    def remove_series(series: Series) -> None:
        chart.series.remove(series)
        controls.refresh()
        changed()

    @ui.refreshable
    def controls() -> None:
        options = _variable_options(config, telemetry)
        x_options = {X_TIME: 'Tempo (s)', X_PACKET: 'Número do pacote', **options}
        if chart.x not in x_options:
            x_options[chart.x] = f'{chart.x} (indisponível)'
        key = 'all' if chart.window_s is None else str(int(chart.window_s))
        window_options = dict(WINDOW_OPTIONS)
        if key not in window_options:
            window_options[key] = f'Últimos {key} s'

        with ui.row().classes('w-full items-end'):
            ui.select(
                x_options, label='Eixo X', value=chart.x, on_change=setter(chart, 'x', changed)
            ).props('outlined dense').classes('w-64')
            ui.select(
                window_options, label='Janela', value=key, on_change=window_changed
            ).props('outlined dense').classes('w-48')
            ui.button('Adicionar variável', icon='add', on_click=add_series).props('outline')

        for series in chart.series:
            y_options = dict(options)
            if series.column not in y_options:
                y_options[series.column] = series.column
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

    updaters.append(update_data)
    option_refreshers.append(controls.refresh)


def _content(
    code: str,
    operation_id: str,
    telemetry: TelemetryService,
    recording: RecordingService,
    configs: TelemetryConfigService,
    session,
) -> None:
    key = operation_id or code  # o rascunho pertence à operação (id), não ao código
    if key in _drafts:
        config = _drafts[key]
    else:
        try:
            config = configs.get(code)
        except (OSError, ValueError, KeyError, TypeError):
            ui.notify('O arquivo de telemetria está ilegível; começando do zero.', type='warning')
            config = TelemetryConfig()
        _drafts[key] = config

    status_rows: list = []  # (esperada, rótulo do valor, rótulo da situação), refeita a cada redesenho
    updaters: list = []
    option_refreshers: list = []
    seen = {'names': frozenset()}
    recording_ui: dict = {}
    last = {'text': ''}

    def from_disk() -> TelemetryConfig:
        try:
            return configs.get(code)
        except (OSError, ValueError, KeyError, TypeError):
            return TelemetryConfig()

    def update_state() -> None:
        dirty = asdict(config) != asdict(from_disk())
        notice.set_visibility(dirty)
        discard_button.set_visibility(dirty)
        save_button.set_enabled(dirty)

    def save() -> None:
        try:
            configs.save(code, config)
        except (OSError, ValueError) as error:
            ui.notify(f'Não foi possível salvar a telemetria: {error}', type='negative')
            return
        update_state()
        ui.notify('Configuração da telemetria salva.', type='positive')

    def discard() -> None:
        discard_dialog.close()
        disk = from_disk()
        config.expected[:] = disk.expected
        config.charts[:] = disk.charts
        expected_list.refresh()
        live_cards.refresh()
        update_state()
        ui.notify('Alterações descartadas.', type='info')

    def expected_changed() -> None:
        update_state()
        live_cards.refresh()  # nomes e unidades aparecem nas legendas

    def add_expected() -> None:
        config.expected.append(ExpectedVariable(''))
        expected_list.refresh()
        update_state()

    def remove_expected(expected) -> None:
        config.expected.remove(expected)
        expected_list.refresh()
        expected_changed()

    def adopt() -> None:
        existing = {e.name for e in config.expected}
        new = [n for n in sorted(telemetry.variables) if n not in existing]
        if not new:
            ui.notify('Nenhuma variável recebida que ainda não esteja na lista.', type='info')
            return
        config.expected.extend(ExpectedVariable(n) for n in new)
        expected_list.refresh()
        expected_changed()

    def remove_chart(chart) -> None:
        config.charts.remove(chart)
        live_cards.refresh()
        update_state()

    def add_chart() -> None:
        config.charts.append(LiveChart.new())
        live_cards.refresh()
        update_state()

    # ---------- gravação ----------

    def start_recording() -> None:
        if not telemetry.connected:
            ui.notify('Conecte a estação na tela Conexão antes de gravar.', type='warning')
            return
        try:
            recording.start(code)
        except OSError as error:
            ui.notify(f'Não foi possível iniciar a gravação: {error}', type='negative')
            return
        last['text'] = ''
        recording_panel.refresh()

    def _conclude(source) -> None:
        last['text'] = (
            f'Gravação finalizada: {source.id} ({source.rows} pacotes). '
            'Os dados já estão disponíveis no Relatório.'
        )
        ui.notify(last['text'], type='positive')
        recording_panel.refresh()
        session.data_changed()  # o Relatório passa a enxergar a fonte nova

    def finish_recording() -> None:
        if not recording.recording:
            return
        owner = recording.code
        target = config if owner == code else configs.get(owner)
        try:
            _conclude(recording.finish_active(target))
        except (ValidationError, OSError) as error:
            ui.notify(f'Não foi possível finalizar a gravação: {error}', type='negative')
            recording_panel.refresh()

    def finish_pending(recording_id: str) -> None:
        try:
            _conclude(recording.finalize(code, recording_id, config))
        except (ValidationError, OSError) as error:
            ui.notify(f'Não foi possível finalizar a gravação: {error}', type='negative')
            recording_panel.refresh()

    def update_recording() -> None:
        if not recording_ui:
            return
        active = recording.recording
        recording_ui['start'].set_enabled(not active)
        recording_ui['finish'].set_enabled(active)
        label = recording_ui['text']
        if active:
            elapsed = int(recording.elapsed_s())
            other = '' if recording.code == code else f' (operação {recording.code})'
            label.set_text(
                f'● Gravando {recording.recording_id}{other} · {recording.count} pacotes · '
                f'{elapsed // 60:02d}:{elapsed % 60:02d}'
            )
            label.classes(replace=RED)
        else:
            label.set_text('Sem gravação ativa')
            label.classes(replace=GRAY)

    @ui.refreshable
    def recording_panel() -> None:
        recording_ui.clear()
        with ui.card().classes('w-full'):
            ui.label('Gravação').classes('text-2xl font-bold')
            for recording_id in recording.pending(code):
                with ui.row().classes('items-center'):
                    ui.label(
                        f'A gravação {recording_id} foi interrompida antes de ser finalizada.'
                    ).classes('text-orange-400')
                    ui.button(
                        'Finalizar gravação interrompida',
                        on_click=lambda i=recording_id: finish_pending(i),
                    ).props('outline')
            with ui.row().classes('items-center'):
                recording_ui['start'] = ui.button(
                    'Iniciar gravação', icon='fiber_manual_record', on_click=start_recording
                )
                recording_ui['finish'] = ui.button(
                    'Finalizar gravação', icon='stop', on_click=finish_recording
                ).props('outline')
                recording_ui['text'] = ui.label('').classes(GRAY)
            if last['text']:
                ui.label(last['text']).classes(GREEN)
                ui.button(
                    'Ir para o Relatório', icon='arrow_forward', on_click=lambda: session.navigate('Relatório')
                ).props('flat')

    # ---------- listas e atualização periódica ----------

    @ui.refreshable
    def expected_list() -> None:
        status_rows.clear()
        if not config.expected:
            ui.label('Nenhuma variável declarada ainda.').classes('text-gray-400')
        for expected in config.expected:
            with ui.row().classes('w-full items-center'):
                ui.input(
                    'Nome (como a estação envia)', value=expected.name,
                    on_change=setter(expected, 'name', expected_changed),
                ).props('outlined dense debounce=500').classes('w-64')
                ui.input(
                    'Nome de exibição', value=expected.label,
                    on_change=setter(expected, 'label', expected_changed),
                ).props('outlined dense debounce=500').classes('w-56')
                ui.input(
                    'Unidade', value=expected.unit,
                    on_change=setter(expected, 'unit', expected_changed),
                ).props('outlined dense debounce=500').classes('w-28')
                value = ui.label('—').classes('w-32 font-mono')
                state = ui.label('').classes('w-44')
                ui.button(icon='close', on_click=lambda e=expected: remove_expected(e)).props(
                    'flat round dense'
                )
                status_rows.append((expected, value, state))

    @ui.refreshable
    def live_cards() -> None:
        updaters.clear()
        option_refreshers.clear()
        if not config.charts:
            ui.label('Nenhum gráfico ainda. Clique em "Adicionar gráfico".').classes('text-gray-400')
        for chart in config.charts:
            _live_card(chart, config, telemetry, update_state, remove_chart, updaters, option_refreshers)

    def tick() -> None:
        update_recording()
        now = time.monotonic()
        if telemetry.connected:
            link_label.set_text(f'Estação conectada a {telemetry.source}.')
            link_label.classes(replace=GREEN)
        else:
            link_label.set_text('Estação desconectada. Conecte na tela Conexão.')
            link_label.classes(replace=GRAY)

        for expected, value_label, state_label in status_rows:
            variable = telemetry.variables.get(expected.name)
            if variable is None:
                value_label.set_text('—')
            else:
                value_label.set_text(f'{variable.value:.6g}' if variable.numeric else str(variable.value))
            if not telemetry.connected:
                text, color = 'desconectada', GRAY
            elif variable is None:
                text, color = 'ainda sem dados', YELLOW
            elif now - variable.updated_at < SILENCE_YELLOW_S:
                text, color = 'recebendo', GREEN
            else:
                text, color = f'sem dados há {now - variable.updated_at:.0f} s', RED
            state_label.set_text(text)
            state_label.classes(replace=f'w-44 {color}')

        declared = {e.name for e in config.expected}
        others.rows = [
            {'name': v.name, 'value': f'{v.value:.6g}' if v.numeric else str(v.value)}
            for v in sorted(telemetry.variables.values(), key=lambda v: v.name)
            if v.name not in declared
        ]
        others.update()

        names = frozenset(telemetry.variables)
        if names != seen['names']:  # chegou variável nova: atualiza as listas dos gráficos
            seen['names'] = names
            for refresh in list(option_refreshers):
                refresh()
        for update in list(updaters):
            update()

    discard_dialog = ui.dialog()
    with discard_dialog, ui.card():
        ui.label('Descartar alterações?').classes('text-lg font-bold')
        ui.label('A configuração volta ao último estado salvo. O que você mudou desde então será perdido.')
        with ui.row().classes('justify-end w-full'):
            ui.button('Cancelar', on_click=discard_dialog.close).props('flat')
            ui.button('Descartar', on_click=discard, color='negative')

    with ui.row().classes('w-full items-center justify-between'):
        link_label = ui.label('').classes(GRAY)
        with ui.row().classes('items-center'):
            notice = ui.label('Alterações não salvas').classes('text-orange-400')
            discard_button = ui.button('Descartar alterações', on_click=discard_dialog.open).props('flat')
            save_button = ui.button('Salvar configuração', icon='save', on_click=save)

    recording_panel()

    with ui.row().classes('w-full items-center justify-between'):
        ui.label('Variáveis esperadas').classes('text-2xl font-bold')
        with ui.row():
            ui.button('Adotar as variáveis recebidas', icon='playlist_add', on_click=adopt).props('outline')
            ui.button('Adicionar variável', icon='add', on_click=add_expected).props('outline')
    expected_list()

    with ui.expansion('Outras variáveis recebidas (não declaradas)').classes('w-full'):
        others = ui.table(
            columns=[
                {'name': 'name', 'label': 'Variável', 'field': 'name', 'align': 'left'},
                {'name': 'value', 'label': 'Valor atual', 'field': 'value', 'align': 'left'},
            ],
            rows=[], row_key='name', pagination=50,
        ).classes('w-full')
        others.props('no-data-label="Nenhuma"')

    ui.separator()

    with ui.row().classes('w-full items-center justify-between'):
        ui.label('Gráficos ao vivo').classes('text-2xl font-bold')
        ui.button('Adicionar gráfico', icon='add_chart', on_click=add_chart).props('outline')
    live_cards()

    update_state()
    ui.timer(0.5, tick)


def build(
    operations: OperationService,
    telemetry: TelemetryService,
    recording: RecordingService,
    configs: TelemetryConfigService,
    session: SessionState,
) -> None:
    operation_page(
        'Telemetria',
        operations,
        session,
        lambda op: _content(op.code, op.id, telemetry, recording, configs, session),
    )