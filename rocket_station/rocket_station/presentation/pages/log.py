from datetime import datetime
from pathlib import Path

import webview
from nicegui import app, ui

from rocket_station.presentation.state.session import SessionState
from rocket_station.application.source_service import SourceService
from rocket_station.domain.data_source import CsvPreview, DataSource
from rocket_station.application.operation_service import OperationService
from rocket_station.presentation.components.operation_page import operation_page

SEPARATOR_NAMES = {',': 'vírgula', ';': 'ponto e vírgula', '\t': 'tabulação'}
RATE_HELP = (
    'Taxa em que o SD gravou as amostras. Se você informar, o Relatório '
    'passa a oferecer o eixo Tempo e as fórmulas que dependem dele.'
)


def _readable_date(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime('%d/%m/%Y %H:%M')
    except ValueError:
        return iso


def _table(labels: list[str], rows: list[list[str]], per_page: int) -> None:
    columns = [{'name': 'n', 'label': 'Amostra', 'field': 'n', 'align': 'left'}]
    columns += [
        {'name': f'c{i}', 'label': label, 'field': f'c{i}', 'align': 'left'}
        for i, label in enumerate(labels)
    ]
    data = [
        {'n': n, **{f'c{i}': value for i, value in enumerate(row)}}
        for n, row in enumerate(rows, start=1)
    ]
    ui.table(columns=columns, rows=data, row_key='n', pagination=per_page).classes(
        'w-full'
    ).props('dense')


def _source_card(code: str, source: DataSource, service: SourceService, refresh, session) -> None:
    names = {c.original: c.display for c in source.columns}
    rate = {'value': source.sample_rate_hz}

    def save() -> None:
        try:
            service.update(code, source.id, names, rate['value'])
        except (ValueError, OSError) as error:
            ui.notify(str(error), type='negative')
            return
        ui.notify('Alterações salvas.', type='positive')
        refresh()
        session.data_changed()

    title = (
        f'{source.id} · {source.origin} · {source.rows} linhas · '
        + (f'{source.sample_rate_hz:g} Hz · ' if source.sample_rate_hz else '')
        + f'importado em {_readable_date(source.imported_at)}'
    )
    with ui.expansion(title).classes('w-full border rounded-lg'):
        with ui.column().classes('w-full p-4'):
            ui.label('Nomes das variáveis').classes('font-bold')
            with ui.grid(columns=3).classes('w-full'):
                for column in source.columns:
                    ui.input(
                        label=column.original,
                        value=column.display,
                        on_change=lambda e, o=column.original: names.update({o: e.value}),
                    ).props('outlined dense')

            ui.number(
                'Taxa de amostragem (Hz), opcional',
                value=source.sample_rate_hz,
                min=0,
                on_change=lambda e: rate.update(value=e.value),
            ).props('outlined dense').classes('w-64')
            ui.label(RATE_HELP).classes('text-gray-400 text-sm')
            ui.button('Salvar alterações', on_click=save).props('outline')

            area = ui.column().classes('w-full')

            def show_data() -> None:
                area.clear()
                with area:
                    try:
                        rows = service.rows(code, source)
                    except (ValueError, OSError) as error:
                        ui.notify(f'Não foi possível ler os dados: {error}', type='negative')
                        return
                    if source.rows > len(rows):
                        ui.label(
                            f'Mostrando as primeiras {len(rows)} de {source.rows} linhas.'
                        ).classes('text-gray-400')
                    _table([c.display for c in source.columns], rows, 50)

            ui.button('Ver dados', icon='table_rows', on_click=show_data).props('flat')


def _content(code: str, service: SourceService, session) -> None:
    dialog = ui.dialog()
    with dialog:
        card = ui.card().style('width: 900px; max-width: 90vw')

    @ui.refreshable
    def sources_list() -> None:
        try:
            sources = service.list_sd(code)
        except (OSError, ValueError, KeyError, TypeError):
            ui.label('Não foi possível ler as fontes desta operação.').classes('text-red-400')
            return
        if not sources:
            ui.label('Nenhum CSV importado nesta operação ainda.').classes('text-gray-400')
            return
        for source in sources:
            _source_card(code, source, service, sources_list.refresh, session)

    def show_preview(file: Path, preview: CsvPreview) -> None:
        names = {column: column for column in preview.columns}
        rate = {'value': None}

        def confirm() -> None:
            try:
                source = service.import_csv(code, file, names, rate['value'])
            except (ValueError, OSError) as error:
                ui.notify(str(error), type='negative')
                return
            dialog.close()
            sources_list.refresh()
            ui.notify(f'{source.origin} importado como {source.id}.', type='positive')
            session.data_changed()

        card.clear()
        with card:
            ui.label('Importar CSV do SD').classes('text-2xl font-bold')
            ui.label(
                f'{file.name} · {preview.total_rows} linhas · {len(preview.columns)} colunas · '
                f'separador: {SEPARATOR_NAMES[preview.separator]}'
            ).classes('text-gray-400')

            ui.label('Nome de cada variável (você pode renomear):').classes('font-bold')
            with ui.grid(columns=3).classes('w-full'):
                for original in preview.columns:
                    ui.input(
                        label=original,
                        value=original,
                        on_change=lambda e, o=original: names.update({o: e.value}),
                    ).props('outlined dense')

            ui.number(
                'Taxa de amostragem (Hz), opcional',
                value=None,
                min=0,
                on_change=lambda e: rate.update(value=e.value),
            ).props('outlined dense').classes('w-64')
            ui.label(RATE_HELP).classes('text-gray-400 text-sm')

            ui.label(f'Primeiras {len(preview.rows)} linhas:').classes('font-bold')
            _table(preview.columns, preview.rows, 20)

            with ui.row().classes('justify-end w-full'):
                ui.button('Cancelar', on_click=dialog.close).props('flat')
                ui.button('Importar', on_click=confirm)
        dialog.open()

    async def import_() -> None:
        result = await app.native.main_window.create_file_dialog(
            webview.FileDialog.OPEN, file_types=('Arquivo CSV (*.csv)',)
        )
        if not result:
            return  # o usuário cancelou
        file = Path(result if isinstance(result, str) else result[0])
        try:
            preview = service.preview(file)
        except (ValueError, OSError) as error:
            ui.notify(f'Não foi possível ler o arquivo: {error}', type='negative')
            return
        show_preview(file, preview)

    with ui.row().classes('w-full items-center justify-between'):
        ui.label('Dados do cartão SD').classes('text-2xl font-bold')
        ui.button('Importar CSV do SD', icon='upload_file', on_click=import_)
    sources_list()


def build(operations: OperationService, service: SourceService, session: SessionState) -> None:
    operation_page('Log', operations, session, lambda op: _content(op.code, service, session))