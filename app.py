from nicegui import app, ui

from src.bootstrap import build_services
from src.config import ASSETS_DIR
from src.ui.shell import build_shell
from src.ui.state.session import SessionState

if not any(getattr(route, 'path', '') == '/assets' for route in app.routes):
    app.add_static_files('/assets', str(ASSETS_DIR))  # logo e fontes, sem internet

build_shell(build_services(), SessionState())

if __name__ in {'__main__', '__mp_main__'}:
    # 720 de altura cabe em notebooks de tela 1366x768
    ui.run(native=True, window_size=(1280, 720), title='Beyond Static Fire', reload=False)