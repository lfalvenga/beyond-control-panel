from dataclasses import asdict

from nicegui import ui

from rocket_station.presentation.state.session import SessionState
from rocket_station.application.operation_service import OperationService
from rocket_station.domain.enums import OperationKind
from rocket_station.domain.errors import (
    OperationExistsError,
    OperationNotFoundError,
    ValidationError,
)
from rocket_station.domain.operation import Parameter
from rocket_station.presentation.labels import KIND_LABELS, REVIEW_LABELS


def _parameter_card(p: Parameter) -> None:
    with ui.expansion().classes('w-full border rounded-lg') as card:
        with card.add_slot('header'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label(p.name).classes('font-bold tracking-wide')
                ui.label().bind_text_from(
                    p, 'review', backward=lambda review: REVIEW_LABELS[review]
                ).classes('text-gray-400')
        with ui.grid(columns=3).classes('w-full p-4'):
            ui.input('Parâmetro', value=p.name).props('outlined readonly')
            ui.input('Unidade').bind_value(p, 'unit').props('outlined')
            ui.number('Valor').bind_value(p, 'value').props('outlined step=any')
            ui.input('Responsável').bind_value(p, 'responsible').props('outlined')
            ui.input('Horário', placeholder='HH:MM').bind_value(p, 'time').props(
                'outlined mask="##:##"'
            )
            ui.select(REVIEW_LABELS, label='Parecer').bind_value(p, 'review').props('outlined')


def build(service: OperationService, session: SessionState) -> None:
    current = {'operation': service.new(), 'editing': False}
    current['original'] = asdict(current['operation'])
    pending = {'code': None}  # para onde ir se o usuário confirmar o descarte
    dialog_exists = ui.dialog()
    dialog_discard = ui.dialog()

    def has_changes() -> bool:
        return asdict(current['operation']) != current['original']

    def reload() -> None:
        code = session.editing_code
        if code is None:
            current['operation'] = service.new()
            current['editing'] = False
        else:
            try:
                current['operation'] = service.get(code)
            except (OperationNotFoundError, OSError, ValueError, KeyError, TypeError):
                ui.notify(f'Não foi possível abrir o teste {code}.', type='negative')
                session.edit(None, force=True)
                return
            current['editing'] = True
        current['original'] = asdict(current['operation'])
        form.refresh()

    def save(replace: bool = False) -> None:
        operation = current['operation']
        try:
            if current['editing']:
                service.update(operation)
            else:
                service.create(operation, replace=replace)
        except OperationExistsError:
            dialog_exists.open()
            return
        except (ValidationError, OperationNotFoundError, OSError) as error:
            ui.notify(str(error), type='negative')
            return
        current['original'] = asdict(operation)
        dialog_exists.close()
        ui.notify(f'Teste {operation.code} salvo.', type='positive')
        session.list_changed()
        session.edit(operation.code)

    def ask(code) -> None:
        if has_changes():
            pending['code'] = code
            dialog_discard.open()
        else:
            session.edit(code, force=True)

    def discard_and_continue() -> None:
        dialog_discard.close()
        session.edit(pending['code'], force=True)

    session.edit_guard = ask

    with dialog_exists, ui.card():
        ui.label('Já existe um teste com esse código.').classes('text-lg font-bold')
        ui.label('Excluir o antigo apaga tudo o que está na pasta dele.')
        with ui.row().classes('justify-end w-full'):
            ui.button('Cancelar', on_click=dialog_exists.close).props('flat')
            ui.button(
                'Excluir o antigo e salvar', on_click=lambda: save(replace=True), color='negative'
            )

    with dialog_discard, ui.card():
        ui.label('Descartar alterações?').classes('text-lg font-bold')
        ui.label('Tudo o que foi digitado e não foi salvo será perdido. Deseja continuar?')
        with ui.row().classes('justify-end w-full'):
            ui.button('Cancelar', on_click=dialog_discard.close).props('flat')
            ui.button('Continuar e descartar', on_click=discard_and_continue, color='negative')

    @ui.refreshable
    def form() -> None:
        op = current['operation']
        editing = current['editing']

        def on_kind_change(event) -> None:
            if event.value == OperationKind.STATIC_TEST:
                op.uses_activation = True

        with ui.row().classes('w-full items-center justify-between'):
            ui.label('Cadastro').classes('text-4xl font-bold')
            with ui.row().classes('items-center'):
                ui.label(f'Editando {op.code}' if editing else 'Criando um teste novo').classes(
                    'text-gray-400'
                )
                ui.button(
                    'Novo teste', icon='add', on_click=lambda: session.request_edit(None)
                ).props('outline')

        with ui.card().classes('w-full'):
            ui.label('Identificação').classes('text-2xl font-bold')
            with ui.grid(columns=3).classes('w-full'):
                code_field = ui.input('Código do Teste').bind_value(op, 'code').props('outlined')
                kind_field = (
                    ui.select(KIND_LABELS, label='Tipo', on_change=on_kind_change)
                    .bind_value(op, 'kind')
                    .props('outlined')
                )
                if editing:  # o código é o nome da pasta, e o tipo muda o sentido do registro
                    code_field.props('readonly')
                    kind_field.props('readonly')
                ui.input('Projeto').bind_value(op, 'project').props('outlined')
                ui.input('Data', placeholder='DD/MM/AAAA').bind_value(op, 'date').props('outlined')
                ui.input('Local').bind_value(op, 'location').props('outlined')
                ui.input('Equipe').bind_value(op, 'team').props('outlined')
                ui.input('Classificação').bind_value(op, 'classification').props('outlined')
                ui.input('Criado por').bind_value(op, 'created_by').props('outlined')
            ui.switch('Usa o circuito de acionamento da Beyond').bind_value(
                op, 'uses_activation'
            ).bind_enabled_from(op, 'kind', backward=lambda kind: kind == OperationKind.FLIGHT)
            ui.textarea('Observações').bind_value(op, 'notes').props('outlined').classes('w-full')

        with ui.card().classes('w-full'):
            ui.label('Ficha de Coleta').classes('text-2xl font-bold')
            for parameter in op.parameters:
                _parameter_card(parameter)

        ui.button('Salvar', on_click=save)

    form()
    session.on_editing_change(reload)