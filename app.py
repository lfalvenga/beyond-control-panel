
from nicegui import app, ui

from src.bootstrap import build_services
from src.config import ASSETS_DIR
from src.ui.shell import build_shell
from src.ui.state.session import SessionState


ASSETS_DIR.mkdir(exist_ok=True)

if not any(getattr(route, 'path', '') == '/assets' for route in app.routes):
    app.add_static_files('/assets', str(ASSETS_DIR))


services = build_services()
session = SessionState()


def root():
    build_shell(services, session)


if __name__ in {'__main__', '__mp_main__'}:
    ui.run(
        root=root,
        native=True,
        window_size=(1280, 720),
        title='Beyond Static Fire',
        reload=False,
    )
