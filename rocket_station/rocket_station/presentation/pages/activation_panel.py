from nicegui import ui

from rocket_station.presentation.state.session import SessionState
from rocket_station.application.activation_service import ActivationService, Notice
from rocket_station.config import SILENCE_YELLOW_S
from rocket_station.domain.activation import StageState
from rocket_station.presentation.theme import GRAY, GREEN, RED, YELLOW

STATE_COLORS = {
    StageState.CONFIRMED: GREEN,
    StageState.SENT: YELLOW,
    StageState.NO_CONFIRMATION: RED,
}


def _show(notices: list[Notice]) -> None:
    for notice in notices:
        extra = {'timeout': 0, 'close_button': 'OK'} if notice.persistent else {}
        ui.notify(notice.text, type=notice.level, **extra)


def build(service: ActivationService, session: SessionState, panel_visible) -> None:
    """Painel de acionamento (numa gaveta à direita, só na Telemetria). Só desenha e chama o serviço."""
    w: dict = {}
    seen = {'journal': 0}

    def reload_history() -> None:
        w['log'].clear()
        code = session.active_code
        for line in service.history_lines(code) if code else []:
            w['log'].push(line)
        seen['journal'] = service.journal_count

    def operation_changed() -> None:
        _show(service.operation_changed())
        reload_history()

    def tick() -> None:
        code = session.active_code
        _show(service.tick(code, panel_visible()))
        lines, seen['journal'] = service.journal_since(seen['journal'])
        for line in lines:
            w['log'].push(line)

        view = service.view(code, panel_visible())
        w['operation'].set_text(f'Operação: {code or "—"}')
        if not view.connected:
            link_text, link_color = 'Estação desconectada', GRAY
        elif view.silence_s is None:
            link_text, link_color = 'Último pacote há —', GRAY
        else:
            link_text = f'Último pacote há {view.silence_s:.1f} s'
            link_color = GREEN if view.silence_s <= SILENCE_YELLOW_S else RED
        w['link'].set_text(link_text)
        w['link'].classes(replace=f'text-sm {link_color}')

        for stage in view.stages:
            w[f'state{stage.number}'].set_text(stage.text)
            w[f'state{stage.number}'].classes(replace=f'text-sm {STATE_COLORS.get(stage.state, GRAY)}')
            w[f'arm{stage.number}'].set_enabled(stage.can_arm)
        w['disarm'].set_enabled(view.connected)
        w['ignite'].set_enabled(view.can_ignite)
        w['blocker'].set_text(f'Bloqueada: {view.ignition_blocker}.' if view.ignition_blocker else '')
        w['countdown'].set_visibility(view.counting)
        w['cancel'].set_visibility(view.counting)
        w['countdown'].set_text(view.countdown_text)
        w['sent'].set_text(f'IGNIÇÃO ENVIADA às {view.ignition_sent_at}' if view.ignition_sent_at else '')
        w['ack4'].set_text(view.ack4_text)

    def on_key(event) -> None:
        if event.key.escape and event.action.keydown:
            _show(service.cancel_countdown('cancelado pelo operador (Esc)'))

    ui.label('ACIONAMENTO').classes('text-xl font-bold tracking-widest')
    w['operation'] = ui.label('').classes('text-gray-400 text-sm')
    w['link'] = ui.label('').classes('text-sm')
    ui.separator()

    for n in (1, 2, 3):
        with ui.card().classes('w-full'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label(f'Estágio {n}').classes('font-bold')
                w[f'state{n}'] = ui.label('').classes('text-sm')
            w[f'arm{n}'] = ui.button(
                f'Armar {n}', on_click=lambda n=n: _show(service.arm(session.active_code, n))
            ).classes('w-full')
    w['disarm'] = ui.button(
        'Desarmar tudo', on_click=lambda: _show(service.disarm(session.active_code))
    ).props('outline color=orange').classes('w-full')

    ui.separator()
    w['ignite'] = ui.button(
        'IGNIÇÃO',
        on_click=lambda: _show(service.start_countdown(session.active_code, panel_visible())),
        color='negative',
    ).classes('w-full text-xl')
    w['blocker'] = ui.label('').classes('text-gray-400 text-sm')
    w['countdown'] = ui.label('').classes('text-3xl font-bold text-red-400 w-full text-center')
    w['cancel'] = ui.button(
        'CANCELAR (Esc)',
        on_click=lambda: _show(service.cancel_countdown('cancelado pelo operador')),
        color='warning',
    ).classes('w-full text-2xl')
    w['sent'] = ui.label('').classes('text-red-400 font-bold')
    w['ack4'] = ui.label('').classes('text-gray-400 text-sm')

    ui.separator()
    ui.label('Eventos').classes('font-bold')
    w['log'] = ui.log(max_lines=60).classes('w-full h-40')

    ui.keyboard(on_key=on_key)
    session.on_active_change(operation_changed)
    ui.timer(0.1, tick)