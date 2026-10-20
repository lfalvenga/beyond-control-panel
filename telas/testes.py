from pathlib import Path

import webview
from nicegui import app, ui

import armazenamento
from armazenamento import Acao, Situacao
from estado import estado
from modelos import ROTULOS_TIPO, Cadastro, Parecer

COLUNAS = [
    {'name': 'ativo', 'label': '', 'field': 'ativo', 'align': 'center'},
    {'name': 'codigo', 'label': 'Código', 'field': 'codigo', 'align': 'left'},
    {'name': 'tipo', 'label': 'Tipo', 'field': 'tipo', 'align': 'left'},
    {'name': 'acionamento', 'label': 'Acionamento', 'field': 'acionamento', 'align': 'left'},
    {'name': 'projeto', 'label': 'Projeto', 'field': 'projeto', 'align': 'left'},
    {'name': 'data', 'label': 'Data', 'field': 'data', 'align': 'left'},
    {'name': 'local', 'label': 'Local', 'field': 'local', 'align': 'left'},
    {'name': 'criado_por', 'label': 'Criado por', 'field': 'criado_por', 'align': 'left'},
    {'name': 'ficha', 'label': 'Ficha', 'field': 'ficha', 'align': 'left'},
]

OPCOES = {
    Situacao.MESMO_TESTE: {
        Acao.PULAR: 'Manter o que já existe',
        Acao.SUBSTITUIR: 'Substituir o existente',
        Acao.MANTER_AMBOS: 'Manter os dois (nova cópia)',
    },
    Situacao.COLISAO: {
        Acao.MANTER_AMBOS: 'Manter os dois (com novo código)',
        Acao.PULAR: 'Pular',
        Acao.SUBSTITUIR: 'Substituir o existente',
    },
}
PADRAO = {Situacao.MESMO_TESTE: Acao.PULAR, Situacao.COLISAO: Acao.MANTER_AMBOS}
AVISO = {
    Situacao.MESMO_TESTE: 'Este teste já existe aqui (mesmo id). Pode ser outra versão dele.',
    Situacao.COLISAO: 'Já existe OUTRO teste com este código.',
}


def _resumo_ficha(cadastro: Cadastro) -> str:
    contagem = {parecer: 0 for parecer in Parecer}
    for parametro in cadastro.ficha:
        contagem[parametro.parecer] += 1
    return (
        f'{contagem[Parecer.DEFERIDO]} deferidos · '
        f'{contagem[Parecer.PENDENTE]} pendentes'
    )


def _descricao(cadastro: Cadastro) -> str:
    i = cadastro.identificacao
    return f'{i.projeto} · {i.data} · {i.local} · por {i.criado_por} · {_resumo_ficha(cadastro)}'


def _linha(cadastro: Cadastro) -> dict:
    ident = cadastro.identificacao
    return {
        'ativo': '●' if ident.codigo == estado.teste_ativo else '',
        'codigo': ident.codigo,
        'tipo': ROTULOS_TIPO[ident.tipo],
        'acionamento': 'Sim' if ident.usa_acionamento else 'Não',
        'projeto': ident.projeto,
        'data': ident.data,
        'local': ident.local,
        'criado_por': ident.criado_por,
        'ficha': _resumo_ficha(cadastro),
    }


def montar():
    dialogo = ui.dialog()
    with dialogo:
        cartao = ui.card().style('width: 800px; max-width: 90vw')

    alvo = {'codigo': None}  # teste que está sendo confirmado para exclusão
    dialogo_excluir = ui.dialog()
    with dialogo_excluir, ui.card():
        ui.label('Excluir teste?').classes('text-lg font-bold')
        texto_exclusao = ui.label()
        with ui.row().classes('justify-end w-full'):
            ui.button('Cancelar', on_click=dialogo_excluir.close).props('flat')
            ui.button('Excluir', on_click=lambda: excluir(), color='negative')

    def atualizar():
        tabela.rows = [_linha(c) for c in armazenamento.listar()]
        tabela.selected.clear()
        tabela.update()

    def _codigo_selecionado() -> str | None:
        if not tabela.selected:
            ui.notify('Selecione um teste na tabela.', type='warning')
            return None
        return tabela.selected[0]['codigo']

    def ativar():
        codigo = _codigo_selecionado()
        if codigo:
            estado.ativar(codigo)

    def editar():
        codigo = _codigo_selecionado()
        if codigo:
            estado.ir('Cadastro')
            estado.pedir_edicao(codigo)

    def pedir_exclusao():
        codigo = _codigo_selecionado()
        if not codigo:
            return
        alvo['codigo'] = codigo
        aviso = (
            f'O teste {codigo} sairá da Biblioteca e será movido para a lixeira '
            f'({armazenamento.PASTA_LIXEIRA}). Nada é apagado de vez.'
        )
        if codigo == estado.teste_ativo:
            aviso += ' Ele é a operação ativa e será desativado.'
        if codigo == estado.em_edicao:
            aviso += ' Ele está aberto no Cadastro, e o formulário será esvaziado.'
        texto_exclusao.set_text(aviso)
        dialogo_excluir.open()

    def excluir():
        codigo = alvo['codigo']
        dialogo_excluir.close()
        try:
            armazenamento.excluir(codigo)
        except (OSError, ValueError) as erro:
            ui.notify(f'Não foi possível excluir: {erro}', type='negative')
            return
        if estado.teste_ativo == codigo:
            estado.ativar(None)
        if estado.em_edicao == codigo:
            estado.editar(None, forcar=True)
        estado.lista_mudou()
        ui.notify(f'Teste {codigo} movido para a lixeira.', type='positive')

    async def exportar():
        codigo = _codigo_selecionado()
        if not codigo:
            return

        resultado = await app.native.main_window.create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename=f'{codigo}{armazenamento.EXTENSAO}',
            file_types=('Pacote de teste (*.beyondtest)',),
        )
        if not resultado:
            return  # o usuário cancelou

        caminho = resultado if isinstance(resultado, str) else resultado[0]
        destino = Path(caminho)
        if destino.suffix != armazenamento.EXTENSAO:
            destino = destino.with_name(destino.name + armazenamento.EXTENSAO)

        try:
            armazenamento.exportar(codigo, destino)
        except (OSError, ValueError) as erro:
            ui.notify(f'Não foi possível exportar: {erro}', type='negative')
            return
        ui.notify(f'Exportado para {destino}', type='positive')

    async def importar():
        caminhos = await app.native.main_window.create_file_dialog(
            webview.FileDialog.OPEN,
            allow_multiple=True,
            file_types=('Pacote de teste (*.beyondtest)',),
        )
        if not caminhos:
            return  # o usuário cancelou
        try:
            pacotes = [armazenamento.verificar_pacote(Path(c)) for c in caminhos]
            mostrar_resumo(pacotes)
        except Exception as erro:
            ui.notify(f'Erro ao preparar a importação: {erro}', type='negative')
            raise

    def mostrar_resumo(pacotes):
        escolhas = {}

        def confirmar():
            importados, falhas = [], []
            for i, pacote in enumerate(pacotes):
                acao = escolhas[i]
                if acao == Acao.PULAR:
                    continue
                try:
                    importados.append(armazenamento.importar_pacote(pacote, acao))
                except Exception as erro:  # a falha de um pacote não pode barrar os outros
                    falhas.append(f'{pacote.arquivo.name}: {erro}')
            dialogo.close()
            estado.lista_mudou()
            # se um teste ativo ou aberto no Cadastro foi substituído, recarrega o que as telas mostram
            if estado.teste_ativo in importados:
                estado.ativar(estado.teste_ativo, forcar=True)
            if estado.em_edicao in importados:
                estado.editar(estado.em_edicao, forcar=True)
            if importados:
                ui.notify(f'Importados: {", ".join(importados)}', type='positive')
            for falha in falhas:
                ui.notify(falha, type='negative')

        cartao.clear()
        with cartao:
            ui.label('Importar testes').classes('text-2xl font-bold')
            for i, pacote in enumerate(pacotes):
                with ui.card().classes('w-full'):
                    ui.label(pacote.arquivo.name).classes('font-bold')

                    if pacote.situacao == Situacao.INVALIDO:
                        ui.label(pacote.erro).classes('text-red-400')
                        escolhas[i] = Acao.PULAR
                        continue

                    ui.label(f'Pacote ({pacote.codigo}): {_descricao(pacote.cadastro)}')

                    if pacote.situacao == Situacao.NOVO:
                        ui.label('Teste novo: será importado.').classes('text-green-400')
                        escolhas[i] = Acao.IMPORTAR
                        continue

                    ui.label(AVISO[pacote.situacao]).classes('text-orange-400')
                    if pacote.existente is not None:
                        ui.label(f'Existente: {_descricao(pacote.existente)}')
                    escolhas[i] = PADRAO[pacote.situacao]
                    ui.select(
                        OPCOES[pacote.situacao],
                        value=PADRAO[pacote.situacao],
                        on_change=lambda e, i=i: escolhas.update({i: e.value}),
                    ).props('outlined').classes('w-full')

            with ui.row().classes('justify-end w-full'):
                ui.button('Cancelar', on_click=dialogo.close).props('flat')
                ui.button('Importar', on_click=confirmar)
        dialogo.open()

    ui.label('Biblioteca').classes('text-4xl font-bold')

    with ui.row().classes('w-full items-center justify-between'):
        ui.label('Testes e voos salvos').classes('text-2xl font-bold')
        with ui.row():
            ui.button('Atualizar', icon='refresh', on_click=atualizar).props('flat')
            ui.button('Ativar', icon='check_circle', on_click=ativar)
            ui.button('Editar', icon='edit', on_click=editar).props('outline')
            ui.button('Excluir', icon='delete', on_click=pedir_exclusao).props('outline color=negative')
            ui.button('Importar', icon='download', on_click=importar).props('outline')
            ui.button('Exportar', icon='upload', on_click=exportar).props('outline')

    tabela = ui.table(
        columns=COLUNAS, rows=[], row_key='codigo', selection='single'
    ).classes('w-full')
    tabela.props('no-data-label="Nenhum teste salvo ainda"')
    atualizar()

    estado.ao_mudar_lista(atualizar)
    estado.ao_mudar_ativo(atualizar)