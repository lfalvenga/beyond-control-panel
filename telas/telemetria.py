import time
from dataclasses import asdict

from nicegui import ui

import graficos
import telemetria_dados as td
from estacao_solo import estacao
from modelos import Cadastro
from telas.comum import tela_com_teste
from telas.estacao import AMARELO, ATRASO_AMARELO, CINZA, VERDE, VERMELHO
from telas.relatorio import EIXO, GRADE, TEXTO, _eixo_y

import gravacao
from estado import estado

# rascunho da configuração por operação (id), ainda não salvo no pacote
_rascunhos: dict[str, td.Telemetria] = {}

OPCOES_JANELA = {
    'tudo': 'Tudo',
    '10': 'Últimos 10 s',
    '30': 'Últimos 30 s',
    '60': 'Últimos 60 s',
    '120': 'Últimos 2 min',
    '300': 'Últimos 5 min',
}


def _ao_mudar(objeto, atributo: str, depois):
    def tratador(evento):
        setattr(objeto, atributo, evento.value)
        depois()

    return tratador


def _rotulo(tel: td.Telemetria, nome: str) -> str:
    for e in tel.esperadas:
        if e.nome == nome:
            texto = e.rotulo or e.nome
            return f'{texto} ({e.unidade})' if e.unidade else texto
    return nome


def _opcoes_variaveis(tel: td.Telemetria) -> dict[str, str]:
    opcoes = {e.nome: _rotulo(tel, e.nome) for e in tel.esperadas if e.nome}
    for v in estacao.variaveis.values():
        if v.numerica and v.nome not in opcoes:
            opcoes[v.nome] = v.nome
    return opcoes


def _opcoes_echart(g: td.GraficoVivo, tel: td.Telemetria) -> dict:
    nomes_por_eixo = {0: [], 1: []}
    for s in g.series:
        nomes_por_eixo[1 if s.eixo == 'direito' else 0].append(_rotulo(tel, s.coluna))
    eixos = [e for e in (0, 1) if nomes_por_eixo[e]] or [0]
    indice = {e: i for i, e in enumerate(eixos)}
    nome_x = {'tempo': 'Tempo (s)', 'seq': 'Número do pacote'}.get(g.x, _rotulo(tel, g.x))
    return {
        'animation': False,  # gráfico ao vivo: sem animação a cada atualização
        'title': {'text': g.titulo, 'left': 'center', 'textStyle': {'color': '#f3f4f6'}},
        'tooltip': {'trigger': 'axis'},
        'legend': {'top': 30, 'textStyle': {'color': TEXTO}},
        'grid': {'left': 70, 'right': 70 if len(eixos) == 2 else 30, 'top': 80, 'bottom': 60},
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
        'series': [
            {
                'name': _rotulo(tel, s.coluna),
                'type': 'line',
                'yAxisIndex': indice[1 if s.eixo == 'direito' else 0],
                'showSymbol': False,
                'lineStyle': {'color': s.cor, 'width': 2},
                'itemStyle': {'color': s.cor},
                'data': [],  # preenchido pelo temporizador
            }
            for s in g.series
        ],
    }


def _card_vivo(g, tel, ao_mudar, remover, atualizadores: list, opcoes_cbs: list) -> None:
    ref = {}

    def atualizar_dados():
        grafico = ref.get('grafico')
        if grafico is None:
            return
        for i, s in enumerate(g.series):
            grafico.options['series'][i]['data'] = estacao.pontos(s.coluna, g.x, g.janela_s)
        grafico.update()

    def desenhar():
        area.clear()
        with area:
            ref['grafico'] = ui.echart(_opcoes_echart(g, tel)).classes('w-full').style('height: 360px')
        atualizar_dados()

    def mudou():
        ao_mudar()
        desenhar()

    def mudou_janela(evento):
        g.janela_s = None if evento.value == 'tudo' else float(evento.value)
        ao_mudar()
        atualizar_dados()

    def adicionar_serie():
        opcoes = _opcoes_variaveis(tel)
        if not opcoes:
            ui.notify('Declare uma variável esperada (ou conecte a estação) primeiro.', type='warning')
            return
        usadas = {s.coluna for s in g.series}
        livre = next((n for n in opcoes if n not in usadas), next(iter(opcoes)))
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
        opcoes = _opcoes_variaveis(tel)
        opcoes_x = {'tempo': 'Tempo (s)', 'seq': 'Número do pacote', **opcoes}
        if g.x not in opcoes_x:
            opcoes_x[g.x] = f'{g.x} (indisponível)'
        chave = 'tudo' if g.janela_s is None else str(int(g.janela_s))
        opcoes_janela = dict(OPCOES_JANELA)
        if chave not in opcoes_janela:
            opcoes_janela[chave] = f'Últimos {chave} s'

        with ui.row().classes('w-full items-end'):
            ui.select(
                opcoes_x, label='Eixo X', value=g.x, on_change=_ao_mudar(g, 'x', mudou)
            ).props('outlined dense').classes('w-64')
            ui.select(
                opcoes_janela, label='Janela', value=chave, on_change=mudou_janela
            ).props('outlined dense').classes('w-48')
            ui.button('Adicionar variável', icon='add', on_click=adicionar_serie).props('outline')

        for serie in g.series:
            opcoes_y = dict(opcoes)
            if serie.coluna not in opcoes_y:
                opcoes_y[serie.coluna] = serie.coluna
            with ui.row().classes('w-full items-center'):
                ui.select(
                    opcoes_y, label='Variável', value=serie.coluna,
                    on_change=_ao_mudar(serie, 'coluna', mudou),
                ).props('outlined dense').classes('w-64')
                ui.select(
                    {'esquerdo': 'Eixo esquerdo', 'direito': 'Eixo direito'}, label='Eixo',
                    value=serie.eixo, on_change=_ao_mudar(serie, 'eixo', mudou),
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

    atualizadores.append(atualizar_dados)
    opcoes_cbs.append(controles.refresh)


def _construir(cadastro: Cadastro) -> None:
    codigo = cadastro.identificacao.codigo
    chave = cadastro.id or codigo  # o rascunho pertence à operação (id), não ao código

    if chave in _rascunhos:
        tel = _rascunhos[chave]
    else:
        try:
            tel = td.carregar(codigo)
        except (OSError, ValueError, KeyError, TypeError):
            ui.notify('O arquivo de telemetria está ilegível; começando do zero.', type='warning')
            tel = td.Telemetria()
        _rascunhos[chave] = tel

    linhas_status: list = []  # (esperada, rótulo do valor, rótulo do estado), refeita a cada redesenho
    atualizadores: list = []
    opcoes_cbs: list = []
    visto = {'nomes': frozenset()}

    def do_disco() -> td.Telemetria:
        try:
            return td.carregar(codigo)
        except (OSError, ValueError, KeyError, TypeError):
            return td.Telemetria()

    def atualizar_estado():
        sujo = asdict(tel) != asdict(do_disco())
        aviso.set_visibility(sujo)
        botao_descartar.set_visibility(sujo)
        botao_salvar.set_enabled(sujo)

    def salvar():
        try:
            td.salvar(codigo, tel)
        except (OSError, ValueError) as erro:
            ui.notify(f'Não foi possível salvar a telemetria: {erro}', type='negative')
            return
        atualizar_estado()
        ui.notify('Configuração da telemetria salva.', type='positive')

    def descartar():
        dialogo_descartar.close()
        disco = do_disco()
        tel.esperadas[:] = disco.esperadas
        tel.graficos[:] = disco.graficos
        lista_esperadas.refresh()
        cartoes_vivos.refresh()
        atualizar_estado()
        ui.notify('Alterações descartadas.', type='info')

    def esperadas_mudaram():
        atualizar_estado()
        cartoes_vivos.refresh()  # os nomes e as unidades aparecem nas legendas

    def adicionar_esperada():
        tel.esperadas.append(td.Esperada(nome=''))
        lista_esperadas.refresh()
        atualizar_estado()

    def remover_esperada(esperada):
        tel.esperadas.remove(esperada)
        lista_esperadas.refresh()
        esperadas_mudaram()

    def adotar():
        existentes = {e.nome for e in tel.esperadas}
        novas = [n for n in sorted(estacao.variaveis) if n not in existentes]
        if not novas:
            ui.notify('Nenhuma variável recebida que ainda não esteja na lista.', type='info')
            return
        tel.esperadas.extend(td.Esperada(nome=n) for n in novas)
        lista_esperadas.refresh()
        esperadas_mudaram()

    def remover_grafico(grafico):
        tel.graficos.remove(grafico)
        cartoes_vivos.refresh()
        atualizar_estado()

    def adicionar_grafico():
        tel.graficos.append(td.novo_grafico())
        cartoes_vivos.refresh()
        atualizar_estado()

    @ui.refreshable
    def lista_esperadas():
        linhas_status.clear()
        if not tel.esperadas:
            ui.label('Nenhuma variável declarada ainda.').classes('text-gray-400')
        for e in tel.esperadas:
            with ui.row().classes('w-full items-center'):
                ui.input(
                    'Nome (como a estação envia)', value=e.nome,
                    on_change=_ao_mudar(e, 'nome', esperadas_mudaram),
                ).props('outlined dense debounce=500').classes('w-64')
                ui.input(
                    'Nome de exibição', value=e.rotulo,
                    on_change=_ao_mudar(e, 'rotulo', esperadas_mudaram),
                ).props('outlined dense debounce=500').classes('w-56')
                ui.input(
                    'Unidade', value=e.unidade,
                    on_change=_ao_mudar(e, 'unidade', esperadas_mudaram),
                ).props('outlined dense debounce=500').classes('w-28')
                valor = ui.label('—').classes('w-32 font-mono')
                situacao = ui.label('').classes('w-44')
                ui.button(icon='close', on_click=lambda e=e: remover_esperada(e)).props('flat round dense')
                linhas_status.append((e, valor, situacao))

    @ui.refreshable
    def cartoes_vivos():
        atualizadores.clear()
        opcoes_cbs.clear()
        if not tel.graficos:
            ui.label('Nenhum gráfico ainda. Clique em "Adicionar gráfico".').classes('text-gray-400')
        for grafico in tel.graficos:
            _card_vivo(grafico, tel, atualizar_estado, remover_grafico, atualizadores, opcoes_cbs)

        # ---------- gravação ----------
    ultima = {'texto': ''}
    gravacao_ui: dict = {}

    def iniciar_gravacao():
        if not estacao.conectada:
            ui.notify('Conecte a estação na tela Conexão antes de gravar.', type='warning')
            return
        identificador, caminho = gravacao.nova_gravacao(codigo)
        estacao.iniciar_gravacao(caminho, codigo, identificador)
        ultima['texto'] = ''
        painel_gravacao.refresh()

    def _concluir(dono: str, identificador: str, alvo: td.Telemetria):
        try:
            fonte = gravacao.finalizar(dono, identificador, alvo)
        except (OSError, ValueError) as erro:
            ui.notify(f'Não foi possível finalizar a gravação: {erro}', type='negative')
            painel_gravacao.refresh()
            return
        ultima['texto'] = (
            f'Gravação finalizada: {fonte.id} ({fonte.linhas} pacotes). '
            'Os dados já estão disponíveis no Relatório.'
        )
        ui.notify(ultima['texto'], type='positive')
        painel_gravacao.refresh()
        estado.dados_mudaram()  # o Relatório passa a enxergar a fonte nova

    def finalizar_gravacao():
        if not estacao.gravando:
            return
        dono, identificador = estacao.gravacao_codigo, estacao.gravacao_ident
        estacao.parar_gravacao()
        _concluir(dono, identificador, tel if dono == codigo else td.carregar(dono))

    def atualizar_gravacao():
        if not gravacao_ui:
            return
        gravando = estacao.gravando
        gravacao_ui['gravar'].set_enabled(not gravando)
        gravacao_ui['finalizar'].set_enabled(gravando)
        texto = gravacao_ui['texto']
        if gravando:
            decorrido = int(time.monotonic() - estacao.gravacao_inicio)
            de_outra = '' if estacao.gravacao_codigo == codigo else f' (operação {estacao.gravacao_codigo})'
            texto.set_text(
                f'● Gravando {estacao.gravacao_ident}{de_outra} · {estacao.gravados} pacotes · '
                f'{decorrido // 60:02d}:{decorrido % 60:02d}'
            )
            texto.classes(replace=VERMELHO)
        else:
            texto.set_text('Sem gravação ativa')
            texto.classes(replace=CINZA)

    @ui.refreshable
    def painel_gravacao():
        gravacao_ui.clear()
        ativa = estacao.gravacao_ident if estacao.gravando and estacao.gravacao_codigo == codigo else ''
        with ui.card().classes('w-full'):
            ui.label('Gravação').classes('text-2xl font-bold')
            for identificador in gravacao.pendentes(codigo, ignorar=ativa):
                with ui.row().classes('items-center'):
                    ui.label(
                        f'A gravação {identificador} foi interrompida antes de ser finalizada.'
                    ).classes('text-orange-400')
                    ui.button(
                        'Finalizar gravação interrompida',
                        on_click=lambda i=identificador: _concluir(codigo, i, tel),
                    ).props('outline')
            with ui.row().classes('items-center'):
                gravacao_ui['gravar'] = ui.button(
                    'Iniciar gravação', icon='fiber_manual_record', on_click=iniciar_gravacao
                )
                gravacao_ui['finalizar'] = ui.button(
                    'Finalizar gravação', icon='stop', on_click=finalizar_gravacao
                ).props('outline')
                gravacao_ui['texto'] = ui.label('').classes(CINZA)
            if ultima['texto']:
                ui.label(ultima['texto']).classes(VERDE)
                ui.button(
                    'Ir para o Relatório', icon='arrow_forward', on_click=lambda: estado.ir('Relatório')
                ).props('flat')

    def tique():
        atualizar_gravacao();
        agora = time.monotonic()
        if estacao.conectada:
            ligacao.set_text(f'Estação conectada a {estacao.fonte}.')
            ligacao.classes(replace=VERDE)
        else:
            ligacao.set_text('Estação desconectada. Conecte na tela Conexão.')
            ligacao.classes(replace=CINZA)

        for e, valor, situacao in linhas_status:
            v = estacao.variaveis.get(e.nome)
            valor.set_text('—' if v is None else f'{v.valor:.6g}' if v.numerica else str(v.valor))
            if not estacao.conectada:
                texto, cor = 'desconectada', CINZA
            elif v is None:
                texto, cor = 'ainda sem dados', AMARELO
            elif agora - v.atualizada_em < ATRASO_AMARELO:
                texto, cor = 'recebendo', VERDE
            else:
                texto, cor = f'sem dados há {agora - v.atualizada_em:.0f} s', VERMELHO
            situacao.set_text(texto)
            situacao.classes(replace=f'w-44 {cor}')

        esperados = {e.nome for e in tel.esperadas}
        outras.rows = [
            {'nome': v.nome, 'valor': f'{v.valor:.6g}' if v.numerica else str(v.valor)}
            for v in sorted(estacao.variaveis.values(), key=lambda v: v.nome)
            if v.nome not in esperados
        ]
        outras.update()

        nomes = frozenset(estacao.variaveis)
        if nomes != visto['nomes']:  # chegou variável nova: atualiza as listas dos gráficos
            visto['nomes'] = nomes
            for atualizar in list(opcoes_cbs):
                atualizar()
        for atualizar in list(atualizadores):
            atualizar()

    dialogo_descartar = ui.dialog()
    with dialogo_descartar, ui.card():
        ui.label('Descartar alterações?').classes('text-lg font-bold')
        ui.label('A configuração volta ao último estado salvo. O que você mudou desde então será perdido.')
        with ui.row().classes('justify-end w-full'):
            ui.button('Cancelar', on_click=dialogo_descartar.close).props('flat')
            ui.button('Descartar', on_click=descartar, color='negative')

    with ui.row().classes('w-full items-center justify-between'):
        ligacao = ui.label('').classes(CINZA)
        with ui.row().classes('items-center'):
            aviso = ui.label('Alterações não salvas').classes('text-orange-400')
            botao_descartar = ui.button(
                'Descartar alterações', on_click=dialogo_descartar.open
            ).props('flat')
            botao_salvar = ui.button('Salvar configuração', icon='save', on_click=salvar)

    with ui.row().classes('w-full items-center justify-between'):
        ui.label('Variáveis esperadas').classes('text-2xl font-bold')
        with ui.row():
            ui.button('Adotar as variáveis recebidas', icon='playlist_add', on_click=adotar).props('outline')
            ui.button('Adicionar variável', icon='add', on_click=adicionar_esperada).props('outline')
    lista_esperadas()

    with ui.expansion('Outras variáveis recebidas (não declaradas)').classes('w-full'):
        outras = ui.table(
            columns=[
                {'name': 'nome', 'label': 'Variável', 'field': 'nome', 'align': 'left'},
                {'name': 'valor', 'label': 'Valor atual', 'field': 'valor', 'align': 'left'},
            ],
            rows=[], row_key='nome', pagination=50,
        ).classes('w-full')
        outras.props('no-data-label="Nenhuma"')
    
    painel_gravacao()
    ui.separator()

    with ui.row().classes('w-full items-center justify-between'):
        ui.label('Gráficos ao vivo').classes('text-2xl font-bold')
        ui.button('Adicionar gráfico', icon='add_chart', on_click=adicionar_grafico).props('outline')
    cartoes_vivos()

    atualizar_estado()
    ui.timer(0.5, tique)


def montar():
    tela_com_teste('Telemetria', construir=_construir)