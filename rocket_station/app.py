from nicegui import ui

from rocket_station.bootstrap import build_services
from rocket_station.presentation.shell import build_shell
from rocket_station.presentation.state.session import SessionState

build_shell(build_services(), SessionState())

if __name__ in {'__main__', '__mp_main__'}:
    # 720 de altura cabe em notebooks de tela 1366x768
    ui.run(native=True, window_size=(1280, 720), title='Beyond Static Fire', reload=False)