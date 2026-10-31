from pathlib import Path

import webview
from nicegui import app, ui

from rocket_station.presentation.state.session import SessionState
from rocket_station.application.operation_service import OperationService
from rocket_station.application.package_service import PackageService
from rocket_station.config import OPERATIONS_DIR, PACKAGE_EXTENSION, TRASH_DIR_NAME
from rocket_station.domain.enums import Review
from rocket_station.domain.errors import OperationNotFoundError
from rocket_station.domain.operation import Operation
from rocket_station.domain.package import ImportAction, ImportSituation
from rocket_station.presentation.labels import KIND_LABELS

FILE_TYPES = ('Pacote de teste (*.beyondtest)',)

COLUMNS = [
    {'name': 'active', 'label': '', 'field': 'active', 'align': 'center'},
    {'name': 'code', 'label': 'Código', 'field': 'code', 'align': 'left'},
    {'name': 'kind', 'label': 'Tipo', 'field': 'kind', 'align': 'left'},
    {'name': 'activation', 'label': 'Acionamento', 'field': 'activation', 'align': 'left'},
    {'name': 'project', 'label': 'Projeto', 'field': 'project', 'align': 'left'},
    {'name': 'date', 'label': 'Data', 'field': 'date', 'align': 'left'},
    {'name': 'location', 'label': 'Local', 'field': 'location', 'align': 'left'},
    {'name': 'created_by', 'label': 'Criado por', 'field': 'created_by', 'align': 'left'},
    {'name': 'review', 'label': 'Ficha', 'field': 'review', 'align': 'left'},
]

OPTIONS = {
    ImportSituation.SAME_OPERATION: {
        ImportAction.SKIP: 'Manter o que já existe',
        ImportAction.REPLACE: 'Substituir o existente',
        ImportAction.KEEP_BOTH: 'Manter os dois (nova cópia)',
    },
    ImportSituation.CODE_CLASH: {
        ImportAction.KEEP_BOTH: 'Manter os dois (com novo código)',
        ImportAction.SKIP: 'Pular',
        ImportAction.REPLACE: 'Substituir o existente',
    },
}
DEFAULT_ACTION = {
    ImportSituation.SAME_OPERATION: ImportAction.SKIP,
    ImportSituation.CODE_CLASH: ImportAction.KEEP_BOTH,
}
NOTICES = {
    ImportSituation.SAME_OPERATION: 'Este teste já existe aqui (mesmo id). Pode ser outra versão dele.',
    ImportSituation.CODE_CLASH: 'Já existe OUTRO teste com este código.',
}


def _review_summary(op: Operation) -> str:
    counts = op.review_counts()
    return f'{counts[Review.APPROVED]} deferidos · {counts[Review.PENDING]} pendentes'


def _description(op: Operation) -> str:
    return f'{op.project} · {op.date} · {op.location} · por {op.created_by} · {_review_summary(op)}'


def _row(op: Operation, session: SessionState) -> dict:
    return {
        'active': '●' if op.code == session.active_code else '',
        'code': op.code,
        'kind': KIND_LABELS[op.kind],
        'activation': 'Sim' if op.uses_activation else 'Não',
        'project': op.project,
        'date': op.date,
        'location': op.location,
        'created_by': op.created_by,
        'review': _review_summary(op),
    }


def build(operations: OperationService, packages: PackageService, session: SessionState) -> None:
    dialog = ui.dialog()
    with dialog:
        card = ui.card().style('width: 800px; max-width: 90vw')

    target = {'code': None}  # teste que está sendo confirmado para exclusão
    delete_dialog = ui.dialog()
    with delete_dialog, ui.card():
        ui.label('Excluir teste?').classes('text-lg font-bold')
        delete_text = ui.label()
        with ui.row().classes('justify-end w-full'):
            ui.button('Cancelar', on_click=delete_dialog.close).props('flat')
            ui.button('Excluir', on_click=lambda: delete(), color='negative')

    def refresh() -> None:
        table.rows = [_row(op, session) for op in operations.list_all()]
        table.selected.clear()
        table.update()

    def selected_code() -> str | None:
        if not table.selected:
            ui.notify('Selecione um teste na tabela.', type='warning')
            return None
        return table.selected[0]['code']

    def activate() -> None:
        code = selected_code()
        if code:
            session.activate(code)

    def edit() -> None:
        code = selected_code()
        if code:
            session.navigate('Cadastro')
            session.request_edit(code)

    def request_delete() -> None:
        code = selected_code()
        if not code:
            return
        target['code'] = code
        text = (
            f'O teste {code} sairá da Biblioteca e será movido para a lixeira '
            f'({OPERATIONS_DIR / TRASH_DIR_NAME}). Nada é apagado de vez.'
        )
        if code == session.active_code:
            text += ' Ele é a operação ativa e será desativado.'
        if code == session.editing_code:
            text += ' Ele está aberto no Cadastro, e o formulário será esvaziado.'
        delete_text.set_text(text)
        delete_dialog.open()

    def delete() -> None:
        code = target['code']
        delete_dialog.close()
        try:
            operations.delete(code)
        except (OperationNotFoundError, OSError) as error:
            ui.notify(f'Não foi possível excluir: {error}', type='negative')
            return
        if session.active_code == code:
            session.activate(None)
        if session.editing_code == code:
            session.edit(None, force=True)
        session.list_changed()
        ui.notify(f'Teste {code} movido para a lixeira.', type='positive')

    async def export_() -> None:
        code = selected_code()
        if not code:
            return
        result = await app.native.main_window.create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename=f'{code}{PACKAGE_EXTENSION}',
            file_types=FILE_TYPES,
        )
        if not result:
            return  # o usuário cancelou
        destination = Path(result if isinstance(result, str) else result[0])
        if destination.suffix != PACKAGE_EXTENSION:
            destination = destination.with_name(destination.name + PACKAGE_EXTENSION)
        try:
            packages.export(code, destination)
        except (OSError, ValueError) as error:
            ui.notify(f'Não foi possível exportar: {error}', type='negative')
            return
        ui.notify(f'Exportado para {destination}', type='positive')

    async def import_() -> None:
        paths = await app.native.main_window.create_file_dialog(
            webview.FileDialog.OPEN, allow_multiple=True, file_types=FILE_TYPES
        )
        if not paths:
            return  # o usuário cancelou
        try:
            show_summary([packages.inspect(Path(p)) for p in paths])
        except Exception as error:
            ui.notify(f'Erro ao preparar a importação: {error}', type='negative')
            raise

    def show_summary(inspections) -> None:
        choices = {}

        def confirm() -> None:
            imported, failures = [], []
            for i, inspection in enumerate(inspections):
                action = choices[i]
                if action == ImportAction.SKIP:
                    continue
                try:
                    imported.append(packages.import_package(inspection, action))
                except Exception as error:  # a falha de um pacote não pode barrar os outros
                    failures.append(f'{inspection.file.name}: {error}')
            dialog.close()
            session.list_changed()
            # se um teste ativo ou aberto no Cadastro foi substituído, recarrega o que as telas mostram
            if session.active_code in imported:
                session.activate(session.active_code, force=True)
            if session.editing_code in imported:
                session.edit(session.editing_code, force=True)
            if imported:
                ui.notify(f'Importados: {", ".join(imported)}', type='positive')
            for failure in failures:
                ui.notify(failure, type='negative')

        card.clear()
        with card:
            ui.label('Importar testes').classes('text-2xl font-bold')
            for i, inspection in enumerate(inspections):
                with ui.card().classes('w-full'):
                    ui.label(inspection.file.name).classes('font-bold')
                    if inspection.situation == ImportSituation.INVALID:
                        ui.label(inspection.error).classes('text-red-400')
                        choices[i] = ImportAction.SKIP
                        continue
                    ui.label(f'Pacote ({inspection.code}): {_description(inspection.operation)}')
                    if inspection.situation == ImportSituation.NEW:
                        ui.label('Teste novo: será importado.').classes('text-green-400')
                        choices[i] = ImportAction.IMPORT
                        continue
                    ui.label(NOTICES[inspection.situation]).classes('text-orange-400')
                    if inspection.existing is not None:
                        ui.label(f'Existente: {_description(inspection.existing)}')
                    choices[i] = DEFAULT_ACTION[inspection.situation]
                    ui.select(
                        OPTIONS[inspection.situation],
                        value=DEFAULT_ACTION[inspection.situation],
                        on_change=lambda e, i=i: choices.update({i: e.value}),
                    ).props('outlined').classes('w-full')
            with ui.row().classes('justify-end w-full'):
                ui.button('Cancelar', on_click=dialog.close).props('flat')
                ui.button('Importar', on_click=confirm)
        dialog.open()

    ui.label('Biblioteca').classes('text-4xl font-bold')
    with ui.row().classes('w-full items-center justify-between'):
        ui.label('Testes e voos salvos').classes('text-2xl font-bold')
        with ui.row():
            ui.button('Atualizar', icon='refresh', on_click=refresh).props('flat')
            ui.button('Ativar', icon='check_circle', on_click=activate)
            ui.button('Editar', icon='edit', on_click=edit).props('outline')
            ui.button('Excluir', icon='delete', on_click=request_delete).props('outline color=negative')
            ui.button('Importar', icon='download', on_click=import_).props('outline')
            ui.button('Exportar', icon='upload', on_click=export_).props('outline')

    table = ui.table(columns=COLUMNS, rows=[], row_key='code', selection='single').classes('w-full')
    table.props('no-data-label="Nenhum teste salvo ainda"')
    refresh()

    session.on_list_change(refresh)
    session.on_active_change(refresh)