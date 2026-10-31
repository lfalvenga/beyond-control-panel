import time

from nicegui import ui

from rocket_station.application.telemetry_service import TelemetryService
from rocket_station.config import (
    BAUD_RATES,
    DELIVERY_GREEN_PCT,
    DELIVERY_YELLOW_PCT,
    RSSI_GREEN_DBM,
    RSSI_YELLOW_DBM,
    SILENCE_GREEN_S,
    SILENCE_YELLOW_S,
)
from rocket_station.presentation.theme import GRAY, GREEN, RED, higher_is_better, lower_is_better


def _indicator(title: str) -> ui.label:
    with ui.card().classes('items-center w-56'):
        ui.label(title).classes('text-gray-400 text-sm')
        return ui.label('—').classes(f'text-3xl font-bold {GRAY}')


def _show(label: ui.label, text: str, color: str) -> None:
    label.set_text(text)
    label.classes(replace=f'text-3xl font-bold {color}')


def build(telemetry: TelemetryService) -> None:
    seen = {'raw': 0}

    def refresh_ports() -> None:
        options = dict(telemetry.ports())
        port.set_options(options, value=port.value if port.value in options else None)

    def toggle() -> None:
        if telemetry.connected:
            telemetry.disconnect()
        else:
            if not port.value:
                ui.notify('Escolha a porta da estação de solo.', type='warning')
                return
            monitor.clear()
            seen['raw'] = 0
            telemetry.connect(port.value, int(baud.value))
        tick()

    def tick() -> None:
        lines, seen['raw'] = telemetry.raw_since(seen['raw'])
        for line in lines:
            monitor.push(line)

        connected = telemetry.connected
        button.set_text('Desconectar' if connected else 'Conectar')
        port.set_enabled(not connected)
        baud.set_enabled(not connected)
        if telemetry.error:
            status.set_text(telemetry.error)
            status.classes(replace=RED)
        elif connected:
            status.set_text(f'Conectado a {telemetry.source}')
            status.classes(replace=GREEN)
        else:
            status.set_text('Desconectado')
            status.classes(replace=GRAY)

        link = telemetry.link
        rssi = link.rssi if connected else None
        silence = telemetry.seconds_since_last_packet if connected else None
        delivery = link.delivery_pct if connected else None
        _show(rssi_label, '—' if rssi is None else f'{rssi:.0f} dBm',
              higher_is_better(rssi, RSSI_GREEN_DBM, RSSI_YELLOW_DBM))
        _show(silence_label, '—' if silence is None else f'{silence:.1f} s',
              lower_is_better(silence, SILENCE_GREEN_S, SILENCE_YELLOW_S))
        _show(delivery_label, '—' if delivery is None else f'{delivery:.0f} %',
              higher_is_better(delivery, DELIVERY_GREEN_PCT, DELIVERY_YELLOW_PCT))
        counters.set_text(f'{link.received} pacotes · {link.invalid} linhas inválidas')

        now = time.monotonic()
        table.rows = [
            {
                'name': v.name,
                'value': f'{v.value:.6g}' if v.numeric else str(v.value),
                'ago': f'{now - v.updated_at:.1f} s',
            }
            for v in sorted(telemetry.variables.values(), key=lambda v: v.name)
        ]
        table.update()

    ui.label('Conexão').classes('text-4xl font-bold')
    with ui.card().classes('w-full'):
        with ui.row().classes('w-full items-end'):
            port = ui.select({}, label='Porta da estação de solo', value=None).props(
                'outlined dense'
            ).classes('w-96')
            ui.button(icon='refresh', on_click=refresh_ports).props('flat round dense')
            baud = ui.select(BAUD_RATES, label='Velocidade (baud)', value=115200).props(
                'outlined dense'
            ).classes('w-44')
            button = ui.button('Conectar', on_click=toggle)
        status = ui.label('Desconectado').classes(GRAY)

    with ui.row().classes('w-full'):
        rssi_label = _indicator('Sinal (RSSI)')
        silence_label = _indicator('Último pacote há')
        delivery_label = _indicator('Entrega de pacotes')
    counters = ui.label().classes(GRAY)

    ui.label('Variáveis recebidas').classes('text-2xl font-bold')
    columns = [
        {'name': 'name', 'label': 'Variável', 'field': 'name', 'align': 'left'},
        {'name': 'value', 'label': 'Valor atual', 'field': 'value', 'align': 'left'},
        {'name': 'ago', 'label': 'Atualizada há', 'field': 'ago', 'align': 'left'},
    ]
    table = ui.table(columns=columns, rows=[], row_key='name', pagination=50).classes('w-full')
    table.props('no-data-label="Nenhuma variável recebida ainda"')

    with ui.expansion('Monitor bruto (para depurar a estação)').classes('w-full'):
        monitor = ui.log(max_lines=200).classes('w-full h-48')

    refresh_ports()
    ui.timer(0.2, tick)