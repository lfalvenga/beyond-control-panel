from datetime import datetime
from pathlib import Path

import webview
from nicegui import app, ui

import fontes
from estado import estado
from modelos import Cadastro
from telas.comum import tela_com_teste

NOMES_SEPARADOR = {',': 'vírgula', ';': 'ponto e vírgula', '\t': 'tabulação'}
AJUDA_TAXA = (
    'Taxa em que o SD gravou as amostras. Se você informar, o Relatório '
    'passa a oferecer o eixo Tempo e as fórmulas que dependem dele.'
)


def _data_legivel(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime('%d/%m/%Y %H:%M')
    except ValueError:
        return iso


def _tabela(rotulos: list[str], linhas: list[list[str]], por_pagina: int) -> None:
    colunas = [{'name': 'n', 'label': 'Amostra', 'field': 'n', 'align': 'left'}]
    colunas += [
        {'name': f'c{i}', 'label': rotulo, 'field': f'c{i}', 'align': 'left'}
        for i, rotulo in enumerate(rotulos)
    ]
    rows = [
        {'n': n, **{f'c{i}': valor for i, valor in enumerate(linha)}}
        for n, linha in enumerate(linhas, start=1)
    ]
    ui.table(
        columns=colunas, rows=rows, row_key='n', pagination=por_pagina
    ).classes('w-full').props('dense')


def _card_fonte(codigo: str, fonte: fontes.Fonte, atualizar) -> None:
    nomes = {c.original: c.exibicao for c in fonte.colunas}
    taxa = {'valor': fonte.taxa_hz}

    def salvar():
        try:
            fontes.atualizar_fonte(codigo, fonte.id, nomes, taxa['valor'])
        except (OSError, ValueError) as erro:
            ui.notify(str(erro), type='negative')
            return
        ui.notify('Alterações salvas.', type='positive')
        atualizar()
        estado.dados_mudaram()

    titulo = (
        f'{fonte.id} · {fonte.origem} · {fonte.linhas} linhas · '
        + (f'{fonte.taxa_hz:g} Hz · ' if fonte.taxa_hz else '')
        + f'importado em {_data_legivel(fonte.importado_em)}'
    )
    with ui.expansion(titulo).classes('w-full border rounded-lg'):
        with ui.column().classes('w-full p-4'):
            ui.label('Nomes das variáveis').classes('font-bold')
            with ui.grid(columns=3).classes('w-full'):
                for coluna in fonte.colunas:
                    ui.input(
                        label=coluna.original,
                        value=coluna.exibicao,
                        on_change=lambda e, o=coluna.original: nomes.update({o: e.value}),
                    ).props('outlined dense')

            ui.number(
                'Taxa de amostragem (Hz), opcional',
                value=fonte.taxa_hz,
                min=0,
                on_change=lambda e: taxa.update(valor=e.value),
            ).props('outlined dense').classes('w-64')
            ui.label(AJUDA_TAXA).classes('text-gray-400 text-sm')
            ui.button('Salvar alterações', on_click=salvar).props('outline')

            area = ui.column().classes('w-full')

            def ver_dados():
                area.clear()
                with area:
                    try:
                        linhas = fontes.ler_linhas(codigo, fonte)
                    except (OSError, ValueError) as erro:
                        ui.notify(f'Não foi possível ler os dados: {erro}', type='negative')
                        return
                    if fonte.linhas > len(linhas):
                        ui.label(
                            f'Mostrando as primeiras {len(linhas)} de {fonte.linhas} linhas.'
                        ).classes('text-gray-400')
                    _tabela([c.exibicao for c in fonte.colunas], linhas, 50)

            ui.button('Ver dados', icon='table_rows', on_click=ver_dados).props('flat')


def _construir(cadastro: Cadastro) -> None:
    codigo = cadastro.identificacao.codigo
    dialogo = ui.dialog()
    with dialogo:
        cartao = ui.card().style('width: 900px; max-width: 90vw')

    @ui.refreshable
    def lista_de_fontes():
        todas = [f for f in fontes.listar_fontes(codigo) if f.tipo == 'sd']
        if not todas:
            ui.label('Nenhum CSV importado nesta operação ainda.').classes('text-gray-400')
            return
        for fonte in todas:
            _card_fonte(codigo, fonte, lista_de_fontes.refresh)

    def mostrar_previa(caminho: Path, previa: fontes.Previa):
        nomes = {coluna: coluna for coluna in previa.colunas}
        taxa = {'valor': None}

        def confirmar():
            try:
                fonte = fontes.importar_csv(codigo, caminho, nomes, taxa['valor'])
            except (OSError, ValueError) as erro:
                ui.notify(str(erro), type='negative')
                return
            dialogo.close()
            lista_de_fontes.refresh()
            ui.notify(f'{fonte.origem} importado como {fonte.id}.', type='positive')
            estado.dados_mudaram()

        cartao.clear()
        with cartao:
            ui.label('Importar CSV do SD').classes('text-2xl font-bold')
            ui.label(
                f'{caminho.name} · {previa.total_linhas} linhas · '
                f'{len(previa.colunas)} colunas · separador: {NOMES_SEPARADOR[previa.separador]}'
            ).classes('text-gray-400')

            ui.label('Nome de cada variável (você pode renomear):').classes('font-bold')
            with ui.grid(columns=3).classes('w-full'):
                for original in previa.colunas:
                    ui.input(
                        label=original,
                        value=original,
                        on_change=lambda e, o=original: nomes.update({o: e.value}),
                    ).props('outlined dense')

            ui.number(
                'Taxa de amostragem (Hz), opcional',
                value=None,
                min=0,
                on_change=lambda e: taxa.update(valor=e.value),
            ).props('outlined dense').classes('w-64')
            ui.label(AJUDA_TAXA).classes('text-gray-400 text-sm')

            ui.label(f'Primeiras {len(previa.linhas)} linhas:').classes('font-bold')
            _tabela(previa.colunas, previa.linhas, 20)

            with ui.row().classes('justify-end w-full'):
                ui.button('Cancelar', on_click=dialogo.close).props('flat')
                ui.button('Importar', on_click=confirmar)
        dialogo.open()

    async def importar():
        resultado = await app.native.main_window.create_file_dialog(
            webview.FileDialog.OPEN,
            file_types=('Arquivo CSV (*.csv)',),
        )
        if not resultado:
            return  # o usuário cancelou
        caminho = Path(resultado if isinstance(resultado, str) else resultado[0])
        try:
            previa = fontes.ler_previa(caminho)
        except (OSError, ValueError) as erro:
            ui.notify(f'Não foi possível ler o arquivo: {erro}', type='negative')
            return
        mostrar_previa(caminho, previa)

    with ui.row().classes('w-full items-center justify-between'):
        ui.label('Dados do cartão SD').classes('text-2xl font-bold')
        ui.button('Importar CSV do SD', icon='upload_file', on_click=importar)
    lista_de_fontes()


def montar():
    tela_com_teste('Log', construir=_construir)