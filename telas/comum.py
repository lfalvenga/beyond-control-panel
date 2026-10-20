from nicegui import ui

import armazenamento
from estado import estado
from modelos import ROTULOS_TIPO


def _carregar_ativo():
    try:
        return armazenamento.carregar(estado.teste_ativo)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def tela_com_teste(
    titulo: str,
    construir=None,
    requer_acionamento: bool = False,
    reagir_a_dados: bool = False,
) -> None:
    """Monta uma tela que só funciona com uma operação ativa.

    construir(cadastro) desenha o conteúdo real da tela. Com requer_acionamento,
    a tela fica bloqueada se a operação não usa o circuito de acionamento da Beyond.
    Com reagir_a_dados, a tela se redesenha quando os CSVs da operação mudam.
    """

    @ui.refreshable
    def conteudo():
        cadastro = _carregar_ativo() if estado.teste_ativo else None

        with ui.row().classes('w-full items-center justify-between'):
            ui.label(titulo).classes('text-4xl font-bold')
            if cadastro is not None:
                ident = cadastro.identificacao
                ui.label(f'{ident.codigo} · {ROTULOS_TIPO[ident.tipo]}').classes(
                    'text-gray-400 tracking-widest'
                )

        if estado.teste_ativo is None:
            ui.label('Selecione uma operação no menu para continuar.').classes('text-gray-400')
            return
        if cadastro is None:
            ui.label(f'Não foi possível abrir {estado.teste_ativo}.').classes('text-red-400')
            return
        if requer_acionamento and not cadastro.identificacao.usa_acionamento:
            ui.label('Esta operação não usa o circuito de acionamento da Beyond.').classes(
                'text-gray-400'
            )
            return
        if construir:
            construir(cadastro)

    conteudo()
    estado.ao_mudar_ativo(conteudo.refresh)
    estado.ao_mudar_lista(conteudo.refresh)  # o cadastro pode ter sido editado e salvo
    if reagir_a_dados:
        estado.ao_mudar_dados(conteudo.refresh)