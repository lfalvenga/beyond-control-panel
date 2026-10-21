import time

from nicegui import ui

from estacao_solo import SIMULADA, estacao

# Limites das faixas de cor. Ajuste aqui por enquanto.
RSSI_VERDE, RSSI_AMARELO = -90.0, -105.0  # dBm (maior é melhor)
ENTREGA_VERDE, ENTREGA_AMARELO = 90.0, 70.0  # % de pacotes recebidos (maior é melhor)
ATRASO_VERDE, ATRASO_AMARELO = 1.0, 3.0  # s desde o último pacote (menor é melhor)

VELOCIDADES = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]
CINZA, VERDE, AMARELO, VERMELHO = 'text-gray-400', 'text-green-400', 'text-yellow-400', 'text-red-400'


def _cor_maior_melhor(valor, verde, amarelo) -> str:
    if valor is None:
        return CINZA
    return VERDE if valor >= verde else AMARELO if valor >= amarelo else VERMELHO


def _cor_menor_melhor(valor, verde, amarelo) -> str:
    if valor is None:
        return CINZA
    return VERDE if valor <= verde else AMARELO if valor <= amarelo else VERMELHO


def _indicador(titulo: str) -> ui.label:
    with ui.card().classes('items-center w-56'):
        ui.label(titulo).classes('text-gray-400 text-sm')
        return ui.label('—').classes(f'text-3xl font-bold {CINZA}')


def _mostrar(rotulo: ui.label, texto: str, cor: str) -> None:
    rotulo.set_text(texto)
    rotulo.classes(replace=f'text-3xl font-bold {cor}')


def montar():
    def atualizar_portas():
        opcoes = {SIMULADA: 'Fonte simulada (sem hardware)'}
        opcoes.update(dict(estacao.portas()))
        fonte.set_options(opcoes, value=fonte.value if fonte.value in opcoes else SIMULADA)

    def alternar():
        if estacao.conectada:
            estacao.desconectar()
        else:
            monitor.clear()
            estacao.conectar(fonte.value, int(velocidade.value))
        atualizar_tela()

    def atualizar_tela():
        for linha in estacao.processar():
            monitor.push(linha)

        conectada = estacao.conectada
        botao.set_text('Desconectar' if conectada else 'Conectar')
        fonte.set_enabled(not conectada)
        velocidade.set_enabled(not conectada)
        if estacao.erro:
            estado.set_text(estacao.erro)
            estado.classes(replace=VERMELHO)
        elif conectada:
            estado.set_text('Conectado' + (' (simulação)' if estacao.fonte == SIMULADA else f' a {estacao.fonte}'))
            estado.classes(replace=VERDE)
        else:
            estado.set_text('Desconectado')
            estado.classes(replace=CINZA)

        rssi = estacao.rssi if conectada else None
        atraso = estacao.sem_pacote_ha if conectada else None
        entrega = estacao.entrega if conectada else None
        _mostrar(rssi_valor, '—' if rssi is None else f'{rssi:.0f} dBm',
                 _cor_maior_melhor(rssi, RSSI_VERDE, RSSI_AMARELO))
        _mostrar(atraso_valor, '—' if atraso is None else f'{atraso:.1f} s',
                 _cor_menor_melhor(atraso, ATRASO_VERDE, ATRASO_AMARELO))
        _mostrar(entrega_valor, '—' if entrega is None else f'{entrega:.0f} %',
                 _cor_maior_melhor(entrega, ENTREGA_VERDE, ENTREGA_AMARELO))
        contadores.set_text(
            f'{estacao.recebidos} pacotes · {estacao.invalidos} linhas inválidas · '
            f'{estacao.ignoradas} mensagens ignoradas'
        )

        agora = time.monotonic()
        tabela.rows = [
            {
                'nome': v.nome,
                'valor': f'{v.valor:.6g}' if v.numerica else str(v.valor),
                'ha': f'{agora - v.atualizada_em:.1f} s',
            }
            for v in sorted(estacao.variaveis.values(), key=lambda v: v.nome)
        ]
        tabela.update()

    ui.label('Conexão').classes('text-4xl font-bold')

    with ui.card().classes('w-full'):
        with ui.row().classes('w-full items-end'):
            fonte = ui.select(
                {SIMULADA: 'Fonte simulada (sem hardware)'},
                label='Porta da estação de solo',
                value=SIMULADA,
            ).props('outlined dense').classes('w-96')
            ui.button(icon='refresh', on_click=atualizar_portas).props('flat round dense')
            velocidade = ui.select(
                VELOCIDADES, label='Velocidade (baud)', value=115200
            ).props('outlined dense').classes('w-44')
            botao = ui.button('Conectar', on_click=alternar)
        estado = ui.label('Desconectado').classes(CINZA)

    with ui.row().classes('w-full'):
        rssi_valor = _indicador('Sinal (RSSI)')
        atraso_valor = _indicador('Último pacote há')
        entrega_valor = _indicador('Entrega de pacotes')
    contadores = ui.label().classes(CINZA)

    ui.label('Variáveis recebidas').classes('text-2xl font-bold')
    colunas = [
        {'name': 'nome', 'label': 'Variável', 'field': 'nome', 'align': 'left'},
        {'name': 'valor', 'label': 'Valor atual', 'field': 'valor', 'align': 'left'},
        {'name': 'ha', 'label': 'Atualizada há', 'field': 'ha', 'align': 'left'},
    ]
    tabela = ui.table(columns=colunas, rows=[], row_key='nome', pagination=50).classes('w-full')
    tabela.props('no-data-label="Nenhuma variável recebida ainda"')

    with ui.expansion('Monitor bruto (para depurar a estação)').classes('w-full'):
        monitor = ui.log(max_lines=200).classes('w-full h-48')

    atualizar_portas()
    ui.timer(0.2, atualizar_tela)