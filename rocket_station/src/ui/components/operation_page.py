from nicegui import ui

from src.application.operation_service import OperationService
from src.domain.errors import OperationNotFoundError
from src.ui.labels import KIND_LABELS
from src.ui.state.session import SessionState


def operation_page(
    title: str,
    operations: OperationService,
    session: SessionState,
    build_content,
    *,
    react_to_data: bool = False,
) -> None:
    """Tela que só funciona com uma operação ativa: cabeçalho, avisos e `build_content(operation)`."""

    @ui.refreshable
    def content() -> None:
        code = session.active_code
        operation = None
        if code is not None:
            try:
                operation = operations.get(code)
            except (OperationNotFoundError, OSError, ValueError, KeyError, TypeError):
                operation = None

        with ui.row().classes('w-full items-center justify-between'):
            ui.label(title).classes('text-4xl font-bold')
            if operation is not None:
                ui.label(f'{operation.code} · {KIND_LABELS[operation.kind]}').classes(
                    'text-gray-400 tracking-widest'
                )
        if code is None:
            ui.label('Selecione uma operação no menu para continuar.').classes('text-gray-400')
            return
        if operation is None:
            ui.label(f'Não foi possível abrir {code}.').classes('text-red-400')
            return
        build_content(operation)

    content()
    session.on_active_change(content.refresh)
    session.on_list_change(content.refresh)  # o cadastro pode ter sido editado e salvo
    if react_to_data:
        session.on_data_change(content.refresh)