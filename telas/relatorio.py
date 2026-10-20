from dataclasses import asdict

import formulas
import fontes
import graficos
import relatorio_dados
from nicegui import ui

from modelos import Cadastro
from telas.calculos_ui import card_calculo, novo_calculo
from telas.comum import tela_com_teste

# rascunho do relatório (gráficos e cálculos) por operação (id), ainda não salvo no pacote
_rascunhos: dict[str, relatorio_dados.Relatorio] = {}

TEXTO = '#d1d5db'
EIXO = '#6b7280'
GRADE = '#1f2937'


def _eixo_y(nome: str, posicao: str, com_grade: bool) -> dict:
    return {
        'type': 'value',
        'name': nome,
        'position': posicao,
        'scale': True,  # não força o zero: dá para ver variações pequenas
        'nameTextStyle': {'color': TEXTO},
        'axisLabel': {'color': TEXTO},
        'axisLine': {'show': True, 'lineStyle': {'color': EIXO}},
        'splitLine': {'show': com_grade, 'lineStyle': {'color': GRADE}},
    }


def _opcoes_echart(g: graficos.Grafico, fonte: fontes.Fonte, numeros: dict) -> dict | None:
    nomes = {c.original: c.exibicao for c in fonte.colunas}
    validas = [s for s in g.series if s.coluna in numeros]
    if not validas:
        return None

    total = len(next(iter(numeros.values())))
    if g.x == 'tempo' and fonte.taxa_hz:
        xs = [i / fonte.taxa_hz for i in range(total)]  # a amostra 1 é o instante zero
        nome_x, ordenado = 'Tempo (s)', True
    elif g.x in numeros:
        xs, nome_x, ordenado = numeros[g.x], nomes.get(g.x, g.x), False
    else:
        xs, nome_x, ordenado = list(range(1, total + 1)), 'Amostra', True

    nomes_por_eixo = {0: [], 1: []}
    for s in validas:
        nomes_por_eixo[1 if s.eixo == 'direito' else 0].append(nomes.get(s.coluna, s.coluna))
    eixos = [e for e in (0, 1) if nomes_por_eixo[e]]  # só cria o eixo que alguém usa
    indice = {e: i for i, e in enumerate(eixos)}

    series = []
    for s in validas:
        eixo = 1 if s.eixo == 'direito' else 0
        serie = {
            'name': nomes.get(s.coluna, s.coluna),
            'type': 'line',
            'yAxisIndex': indice[eixo],
            'showSymbol': False,
            'lineStyle': {'color': s.cor, 'width': 2},
            'itemStyle': {'color': s.cor},
            'data': [[x, y] for x, y in zip(xs, numeros[s.coluna]) if x is not None],
        }
        if ordenado:
            serie['sampling'] = 'lttb'  # reduz a densidade só na exibição
        series.append(serie)

    return {
        'title': {'text': g.titulo, 'left': 'center', 'textStyle': {'color': '#f3f4f6'}},
        'tooltip': {'trigger': 'axis'},
        'legend': {'top': 30, 'textStyle': {'color': TEXTO}},
        'toolbox': {
            'right': 10,
            'feature': {'restore': {'title': 'Restaurar zoom'}},
            'iconStyle': {'borderColor': TEXTO},
        },
        'grid': {'left': 70, 'right': 70 if len(eixos) == 2 else 30, 'top': 80, 'bottom': 95},
        'dataZoom': [
            {'type': 'inside', 'xAxisIndex': 0},
            {'type': 'slider', 'xAxisIndex': 0, 'textStyle': {'color': TEXTO}},
        ],
        'xAxis': {
            'type': 'value',
            'name': nome_x,
            'nameLocation': 'middle',
            'nameGap': 30,
            'scale': True,
            'nameTextStyle': {'color': TEXTO},
            'axisLabel': {'color': TEXTO},
            'axisLine': {'lineStyle': {'color': EIXO}},
            'splitLine': {'show': False},
        },
        'yAxis': [
            _eixo_y(' / '.join(nomes_por_eixo[e]), 'left' if e == 0 else 'right', e == eixos[0])
            for e in eixos
        ],
        'series': series,
    }

def _ao_mudar(objeto, atributo: str, depois):
    """Devolve um tratador que grava o novo valor no objeto e chama `depois`."""

    def tratador(evento):
        setattr(objeto, atributo, evento.value)
        depois()

    return tratador


def _card_grafico(codigo: str, g: graficos.Grafico, todas_fontes: list, ao_mudar, remover) -> None:
    por_id = {f.id: f for f in todas_fontes}

    def dados_da_fonte():
        fonte = por_id.get(g.fonte)
        if fonte is None:
            return None, {}
        try:
            return fonte, fontes.carregar_numeros(codigo, fonte)
        except (OSError, ValueError):
            return fonte, {}

    def desenhar():
        area.clear()
        with area:
            fonte, numeros = dados_da_fonte()
            if fonte is None:
                ui.label('A fonte deste gráfico não existe mais. Escolha outra.').classes(
                    'text-orange-400'
                )
                return
            if not numeros:
                ui.label(
                    'Esta fonte não tem colunas numéricas (ou não foi possível lê-la).'
                ).classes('text-orange-400')
                return
            opcoes = _opcoes_echart(g, fonte, numeros)
            if opcoes is None:
                ui.label('Adicione ao menos uma variável para o eixo Y.').classes('text-gray-400')
                return
            ui.echart(opcoes).classes('w-full').style('height: 440px')

    def mudou():
        ao_mudar()
        desenhar()

    def trocar_fonte(evento):
        g.fonte = evento.value
        nova = por_id.get(g.fonte)
        _, numeros = dados_da_fonte()
        # aproveita as variáveis que também existem na nova fonte
        g.series = [s for s in g.series if s.coluna in numeros]
        tempo_ok = g.x == 'tempo' and nova is not None and bool(nova.taxa_hz)
        if g.x != 'amostra' and g.x not in numeros and not tempo_ok:
            g.x = 'amostra'
        controles.refresh()
        mudou()

    def adicionar_serie():
        _, numeros = dados_da_fonte()
        if not numeros:
            ui.notify('Esta fonte não tem colunas numéricas.', type='warning')
            return
        usadas = {s.coluna for s in g.series}
        livre = next((c for c in numeros if c not in usadas), next(iter(numeros)))
        cor = graficos.PALETA[len(g.series) % len(graficos.PALETA)]
        g.series.append(graficos.Serie(coluna=livre, eixo='esquerdo', cor=cor))
        controles.refresh()
        mudou()

    def remover_serie(serie):
        g.series.remove(serie)
        controles.refresh()
        mudou()

    @ui.refreshable
    def controles():
        fonte, numeros = dados_da_fonte()
        nomes = {c.original: c.exibicao for c in fonte.colunas} if fonte else {}
        variaveis = {coluna: nomes.get(coluna, coluna) for coluna in numeros}

        opcoes_fonte = {f.id: f'{f.id} · {f.origem}' for f in todas_fontes}
        if g.fonte not in opcoes_fonte:
            opcoes_fonte[g.fonte] = f'{g.fonte} (indisponível)'
        opcoes_x = {'amostra': 'Amostra'}
        if fonte is not None and fonte.taxa_hz:
            opcoes_x['tempo'] = 'Tempo (s)'  # só existe se a fonte tiver taxa
        opcoes_x.update(variaveis)
        if g.x not in opcoes_x:
            opcoes_x[g.x] = f'{g.x} (indisponível)'

        with ui.row().classes('w-full items-end'):
            ui.select(
                opcoes_fonte, label='Fonte', value=g.fonte, on_change=trocar_fonte
            ).props('outlined dense').classes('w-64')
            ui.select(
                opcoes_x, label='Eixo X', value=g.x, on_change=_ao_mudar(g, 'x', mudou)
            ).props('outlined dense').classes('w-64')
            ui.button('Adicionar variável', icon='add', on_click=adicionar_serie).props('outline')

        for serie in g.series:
            opcoes_y = dict(variaveis)
            if serie.coluna not in opcoes_y:
                opcoes_y[serie.coluna] = f'{serie.coluna} (indisponível)'
            with ui.row().classes('w-full items-center'):
                ui.select(
                    opcoes_y,
                    label='Variável',
                    value=serie.coluna,
                    on_change=_ao_mudar(serie, 'coluna', mudou),
                ).props('outlined dense').classes('w-64')
                ui.select(
                    {'esquerdo': 'Eixo esquerdo', 'direito': 'Eixo direito'},
                    label='Eixo',
                    value=serie.eixo,
                    on_change=_ao_mudar(serie, 'eixo', mudou),
                ).props('outlined dense').classes('w-48')
                ui.color_input(
                    'Cor', value=serie.cor, preview=True, on_change=_ao_mudar(serie, 'cor', mudou)
                ).classes('w-40')
                ui.button(
                    icon='close', on_click=lambda s=serie: remover_serie(s)
                ).props('flat round dense')

    with ui.card().classes('w-full'):
        with ui.row().classes('w-full items-center justify-between'):
            ui.input(
                'Título', value=g.titulo, on_change=_ao_mudar(g, 'titulo', lambda: mudou())
            ).props('outlined dense debounce=500').classes('grow')
            ui.button(
                'Remover gráfico', icon='delete', on_click=lambda: remover(g)
            ).props('flat color=negative')
        controles()
        area = ui.column().classes('w-full')
        desenhar()
        ui.textarea(
            'Observações', value=g.observacao, on_change=_ao_mudar(g, 'observacao', ao_mudar)
        ).props('outlined autogrow debounce=500').classes('w-full')

def _construir(cadastro: Cadastro) -> None:
    codigo = cadastro.identificacao.codigo
    chave = cadastro.id or codigo  # o rascunho pertence à operação (id), não ao código
    try:
        todas_fontes = fontes.listar_fontes(codigo)
    except (OSError, ValueError, KeyError, TypeError):
        ui.label('Não foi possível ler as fontes de dados desta operação.').classes('text-red-400')
        return
    if not todas_fontes:
        ui.label('Importe um CSV do SD na tela Log para montar gráficos e cálculos.').classes(
            'text-gray-400'
        )
        return

    disponiveis = formulas.carregar_formulas()

    if chave in _rascunhos:
        rel = _rascunhos[chave]  # volta ao que estava sendo editado, salvo ou não
    else:
        try:
            rel = relatorio_dados.carregar(codigo)
        except (OSError, ValueError, KeyError, TypeError):
            ui.notify('O arquivo do relatório está ilegível; começando do zero.', type='warning')
            rel = relatorio_dados.Relatorio()
        _rascunhos[chave] = rel

    def do_disco() -> relatorio_dados.Relatorio:
        try:
            return relatorio_dados.carregar(codigo)
        except (OSError, ValueError, KeyError, TypeError):
            return relatorio_dados.Relatorio()

    def ha_alteracoes() -> bool:
        return asdict(rel) != asdict(do_disco())

    def atualizar_estado():
        sujo = ha_alteracoes()
        aviso.set_visibility(sujo)
        botao_descartar.set_visibility(sujo)
        botao_salvar.set_enabled(sujo)

    def salvar():
        try:
            relatorio_dados.salvar(codigo, rel)
        except (OSError, ValueError) as erro:
            ui.notify(f'Não foi possível salvar o relatório: {erro}', type='negative')
            return
        atualizar_estado()
        ui.notify('Relatório salvo.', type='positive')

    def descartar():
        dialogo_descartar.close()
        disco = do_disco()
        rel.graficos[:] = disco.graficos  # troca o conteúdo das mesmas listas
        rel.calculos[:] = disco.calculos
        cartoes_graficos.refresh()
        cartoes_calculos.refresh()
        atualizar_estado()
        ui.notify('Alterações descartadas.', type='info')

    def remover_grafico(grafico):
        rel.graficos.remove(grafico)
        cartoes_graficos.refresh()
        atualizar_estado()

    def adicionar_grafico():
        fonte = todas_fontes[-1]  # a importada por último
        try:
            numeros = fontes.carregar_numeros(codigo, fonte)
        except (OSError, ValueError):
            numeros = {}
        rel.graficos.append(graficos.novo_grafico(fonte.id, next(iter(numeros), None)))
        cartoes_graficos.refresh()
        atualizar_estado()

    def remover_calculo(calculo):
        rel.calculos.remove(calculo)
        cartoes_calculos.refresh()
        atualizar_estado()

    def adicionar_calculo():
        if not disponiveis:
            ui.notify('Não há fórmulas instaladas. Veja formulas/_modelo.py.', type='warning')
            return
        rel.calculos.append(novo_calculo(disponiveis, todas_fontes[-1].id))
        cartoes_calculos.refresh()
        atualizar_estado()

    @ui.refreshable
    def cartoes_graficos():
        if not rel.graficos:
            ui.label('Nenhum gráfico ainda. Clique em "Adicionar gráfico".').classes('text-gray-400')
        for grafico in rel.graficos:
            _card_grafico(codigo, grafico, todas_fontes, atualizar_estado, remover_grafico)

    @ui.refreshable
    def cartoes_calculos():
        if not rel.calculos:
            ui.label('Nenhum cálculo ainda. Clique em "Adicionar cálculo".').classes('text-gray-400')
        for calculo in rel.calculos:
            card_calculo(
                codigo, calculo, todas_fontes, disponiveis, atualizar_estado, remover_calculo
            )

    dialogo_descartar = ui.dialog()
    with dialogo_descartar, ui.card():
        ui.label('Descartar alterações?').classes('text-lg font-bold')
        ui.label('O relatório volta ao último estado salvo. O que você mudou desde então será perdido.')
        with ui.row().classes('justify-end w-full'):
            ui.button('Cancelar', on_click=dialogo_descartar.close).props('flat')
            ui.button('Descartar', on_click=descartar, color='negative')

    with ui.row().classes('w-full items-center justify-end'):
        aviso = ui.label('Alterações não salvas').classes('text-orange-400')
        botao_descartar = ui.button(
            'Descartar alterações', on_click=dialogo_descartar.open
        ).props('flat')
        botao_salvar = ui.button('Salvar relatório', icon='save', on_click=salvar)

    with ui.row().classes('w-full items-center justify-between'):
        ui.label('Gráficos').classes('text-2xl font-bold')
        ui.button('Adicionar gráfico', icon='add_chart', on_click=adicionar_grafico).props('outline')
    cartoes_graficos()

    ui.separator()

    with ui.row().classes('w-full items-center justify-between'):
        ui.label('Cálculos').classes('text-2xl font-bold')
        ui.button('Adicionar cálculo', icon='calculate', on_click=adicionar_calculo).props('outline')
    for arquivo, motivo in formulas.erros_de_carga().items():
        ui.label(f'A fórmula "{arquivo}" não pôde ser carregada: {motivo}').classes('text-orange-400')
    if not disponiveis:
        ui.label(
            'Nenhuma fórmula encontrada na pasta formulas/. Veja formulas/_modelo.py para criar a primeira.'
        ).classes('text-gray-400')
    cartoes_calculos()

    atualizar_estado()
    
def montar():
    tela_com_teste('Relatório', construir=_construir, reagir_a_dados=True)