from nicegui import ui

import armazenamento
from estado import estado
from telas import cadastro, estacao, log, painel_acionamento, relatorio, telemetria, testes
TELAS = {
    'Cadastro': cadastro,
    'Biblioteca': testes,
    'Telemetria': telemetria,
    'Log': log,
    'Relatório': relatorio,
    'Conexão': estacao,
}
GRUPO_DOCUMENTACAO = ('Cadastro', 'Biblioteca')
GRUPO_OPERACAO = ('Telemetria', 'Log', 'Relatório')
GRUPO_ESTACAO = ('Conexão',)

estado.reiniciar()

ui.dark_mode().enable()
ui.query('body').style('background-color: #000000')

itens = {}


def ir(nome: str) -> None:
    paineis.set_value(nome)
    for n, item in itens.items():
        if n == nome:
            item.props('active')
        else:
            item.props(remove='active')

    _atualizar_painel();


estado.ir = ir

usa_acionamento_ativa = {'valor': False}


def _atualizar_painel() -> None:
    mostrar = (
        paineis.value == 'Telemetria'
        and estado.teste_ativo is not None
        and usa_acionamento_ativa['valor']
    )
    if mostrar:
        painel_direito.show()
    else:
        painel_direito.hide()


def _item_de_menu(nome: str) -> None:
    itens[nome] = ui.item(nome, on_click=lambda: ir(nome)).props(
        'active-class="bg-slate-700"'
    )


def _opcoes_do_seletor() -> dict:
    opcoes = {}
    for c in armazenamento.listar():
        i = c.identificacao
        opcoes[i.codigo] = ' · '.join(filter(None, [i.codigo, i.projeto]))
    return opcoes


def _atualizar_seletor() -> None:
    opcoes = _opcoes_do_seletor()
    valor = estado.teste_ativo if estado.teste_ativo in opcoes else None
    seletor.set_options(opcoes, value=valor)


def _atualizar_menu() -> None:
    """Mostra o item Acionamento só se a operação ativa usa o circuito da Beyond."""
    usa_acionamento = True  # sem operação ativa, o item continua à vista
    if estado.teste_ativo is not None:
        try:
            ativa = armazenamento.carregar(estado.teste_ativo)
            usa_acionamento = ativa.identificacao.usa_acionamento
        except (OSError, ValueError, KeyError, TypeError):
            usa_acionamento = True
    usa_acionamento_ativa['valor'] = estado.teste_ativo is not None and usa_acionamento
    _atualizar_painel()
   


def _ao_escolher(evento) -> None:
    if evento.value != estado.teste_ativo:
        estado.ativar(evento.value)


with ui.left_drawer(fixed=True).props('width=270').classes('bg-slate-900'):
    ui.label('BEYOND').classes('text-2xl font-bold tracking-widest')
    ui.label('STATIC FIRE').classes('text-xs tracking-widest text-gray-400 mt-6 mb-2')

    with ui.expansion('Documentação', icon='description', value=True).classes('w-full'):
        for nome in GRUPO_DOCUMENTACAO:
            _item_de_menu(nome)

    with ui.expansion('Operação', icon='rocket_launch', value=True).classes('w-full'):
        seletor = (
            ui.select({}, label='Operação ativa', value=None, on_change=_ao_escolher)
            .props('outlined dense')
            .classes('w-full')
        )
        for nome in GRUPO_OPERACAO:
            _item_de_menu(nome)

    with ui.expansion('Estação', icon='cell_tower', value=True).classes('w-full'):
        for nome in GRUPO_ESTACAO:
            _item_de_menu(nome)

with ui.right_drawer(value=False, fixed=True).props('width=320 bordered breakpoint=700').classes(
    'bg-slate-900'
) as painel_direito:
    painel_acionamento.montar(lambda: painel_direito.value)

with ui.tab_panels(value='Cadastro').classes('w-full bg-transparent') as paineis:
    for nome, tela in TELAS.items():
        with ui.tab_panel(nome):
            tela.montar()



estado.ao_mudar_ativo(_atualizar_seletor)
estado.ao_mudar_ativo(_atualizar_menu)
estado.ao_mudar_lista(_atualizar_seletor)
estado.ao_mudar_lista(_atualizar_menu)
_atualizar_seletor()
_atualizar_menu()
ir('Cadastro')

if __name__ in {'__main__', '__mp_main__'}:
    ui.run(
        native=True,
        window_size=(1280, 800),
        title='Beyond Static Fire',
        reload=False,
    )