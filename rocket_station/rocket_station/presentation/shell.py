from nicegui import ui

from rocket_station.bootstrap import Services
from rocket_station.domain.errors import OperationNotFoundError
from rocket_station.presentation.pages import (
    activation_panel,
    connection,
    library,
    log,
    registration,
    report,
    telemetry,
)
from rocket_station.presentation.state.session import SessionState

# (grupo, ícone, itens). O seletor da operação ativa fica no topo do grupo "Operação".
MENU = [
    ('Documentação', 'description', ['Cadastro', 'Biblioteca']),
    ('Operação', 'rocket_launch', ['Telemetria', 'Log', 'Relatório']),
    ('Estação', 'cell_tower', ['Conexão']),
]


def build_shell(services: Services, session: SessionState) -> None:
    ops = services.operations
    pages = {
        'Cadastro': lambda: registration.build(ops, session),
        'Biblioteca': lambda: library.build(ops, services.packages, session),
        'Telemetria': lambda: telemetry.build(
            ops, services.telemetry, services.recording, services.telemetry_config, session
        ),
        'Log': lambda: log.build(ops, services.sources, session),
        'Relatório': lambda: report.build(
            ops, services.report, services.sources, services.calculations, session
        ),
        'Conexão': lambda: connection.build(services.telemetry),
    }
    items: dict = {}

    def uses_activation() -> bool:
        code = session.active_code
        if code is None:
            return False
        try:
            return ops.get(code).uses_activation
        except (OperationNotFoundError, OSError, ValueError, KeyError, TypeError):
            return False

    def update_activation_panel() -> None:
        if panels.value == 'Telemetria' and uses_activation():
            right_drawer.show()
        else:
            right_drawer.hide()

    def navigate(name: str) -> None:
        panels.set_value(name)
        for key, item in items.items():
            if key == name:
                item.props('active')
            else:
                item.props(remove='active')
        update_activation_panel()

    def selector_options() -> dict[str, str]:
        return {
            op.code: ' · '.join(filter(None, [op.code, op.project])) for op in ops.list_all()
        }

    def refresh_selector() -> None:
        options = selector_options()
        selector.set_options(
            options, value=session.active_code if session.active_code in options else None
        )

    def on_select(event) -> None:
        if event.value != session.active_code:
            session.activate(event.value)

    ui.dark_mode().enable()
    ui.query('body').style('background-color: #000000')

    with ui.left_drawer(fixed=True).props('width=270').classes('bg-slate-900'):
        ui.label('BEYOND').classes('text-2xl font-bold tracking-widest')
        ui.label('STATIC FIRE').classes('text-xs tracking-widest text-gray-400 mt-6 mb-2')
        for group, icon, names in MENU:
            with ui.expansion(group, icon=icon, value=True).classes('w-full'):
                if group == 'Operação':
                    selector = (
                        ui.select({}, label='Operação ativa', value=None, on_change=on_select)
                        .props('outlined dense')
                        .classes('w-full')
                    )
                for name in names:
                    items[name] = ui.item(name, on_click=lambda name=name: navigate(name)).props(
                        'active-class="bg-slate-700"'
                    )

    with ui.right_drawer(value=False, fixed=True).props('width=320 bordered breakpoint=700').classes(
        'bg-slate-900'
    ) as right_drawer:
        activation_panel.build(services.activation, session, lambda: right_drawer.value)

    with ui.tab_panels(value='Cadastro').classes('w-full bg-transparent') as panels:
        for name, build_page in pages.items():
            with ui.tab_panel(name):
                build_page()

    session.navigate = navigate
    for register in (session.on_active_change, session.on_list_change):
        register(refresh_selector)
        register(update_activation_panel)
    refresh_selector()
    navigate('Cadastro')
    ui.timer(0.1, services.telemetry.poll)  # lê a estação mesmo com a tela da Conexão fechada