from dataclasses import asdict

from nicegui import ui

import armazenamento
from estado import estado
from modelos import ROTULOS_TIPO, Cadastro, Parametro, Parecer, Tipo, nova_ficha


def _card_parametro(p: Parametro):
    with ui.expansion().classes('w-full border rounded-lg') as card:
        with card.add_slot('header'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label(p.nome).classes('font-bold tracking-wide')
                ui.label().bind_text_from(
                    p, 'parecer', backward=lambda parecer: parecer.value
                ).classes('text-gray-400')

        with ui.grid(columns=3).classes('w-full p-4'):
            ui.input('Parâmetro', value=p.nome).props('outlined readonly')
            ui.input('Unidade').bind_value(p, 'unidade').props('outlined')
            ui.number('Valor').bind_value(p, 'valor').props('outlined step=any')
            ui.input('Responsável').bind_value(p, 'responsavel').props('outlined')
            ui.input('Horário', placeholder='HH:MM').bind_value(p, 'horario').props(
                'outlined mask="##:##"'
            )
            ui.select(
                {opcao: opcao.value for opcao in Parecer}, label='Parecer'
            ).bind_value(p, 'parecer').props('outlined')


def montar():
    atual = {
        'cadastro': Cadastro(ficha=nova_ficha()),
        'editando': False,
        # retrato do que está salvo (ou do formulário em branco), para detectar alterações
        'original': asdict(Cadastro(ficha=nova_ficha())),
    }
    destino_pendente = {'codigo': None}  # para onde ir se o usuário confirmar o descarte
    dialogo = ui.dialog()
    dialogo_descartar = ui.dialog()

    def tem_alteracoes() -> bool:
        return asdict(atual['cadastro']) != atual['original']

    def recarregar():
        """Roda quando o teste em edição muda: abre esse teste, ou um formulário em branco."""
        codigo = estado.em_edicao
        if codigo is None:
            atual['cadastro'] = Cadastro(ficha=nova_ficha())
            atual['editando'] = False
        else:
            try:
                atual['cadastro'] = armazenamento.carregar(codigo)
            except (OSError, ValueError, KeyError, TypeError):
                ui.notify(f'Não foi possível abrir o teste {codigo}.', type='negative')
                estado.editar(None, forcar=True)  # volta ao formulário em branco
                return
            atual['editando'] = True
        atual['original'] = asdict(atual['cadastro'])
        formulario.refresh()

    def gravar(substituir: bool = False):
        cadastro = atual['cadastro']
        try:
            if atual['editando']:
                codigo = armazenamento.atualizar(cadastro)
            else:
                codigo = armazenamento.salvar(cadastro, substituir=substituir).name
        except FileExistsError:
            dialogo.open()
            return
        except (ValueError, OSError) as erro:
            ui.notify(str(erro), type='negative')
            return
        atual['original'] = asdict(cadastro)  # agora o que está na tela é o que está salvo
        dialogo.close()
        ui.notify(f'Teste {codigo} salvo.', type='positive')
        estado.lista_mudou()
        estado.editar(codigo)  # um teste recém-criado passa a ser mostrado como "em edição"

    def pedir(codigo):
        """Guarda da edição: se há alterações não salvas, pergunta antes de trocar."""
        if tem_alteracoes():
            destino_pendente['codigo'] = codigo
            dialogo_descartar.open()
        else:
            estado.editar(codigo, forcar=True)

    def descartar_e_continuar():
        dialogo_descartar.close()
        estado.editar(destino_pendente['codigo'], forcar=True)

    estado.guarda_edicao = pedir

    with dialogo, ui.card():
        ui.label('Já existe um teste com esse código.').classes('text-lg font-bold')
        ui.label('Excluir o antigo apaga tudo o que está na pasta dele.')
        with ui.row().classes('justify-end w-full'):
            ui.button('Cancelar', on_click=dialogo.close).props('flat')
            ui.button(
                'Excluir o antigo e salvar',
                on_click=lambda: gravar(substituir=True),
                color='negative',
            )

    with dialogo_descartar, ui.card():
        ui.label('Descartar alterações?').classes('text-lg font-bold')
        ui.label('Tudo o que foi digitado e não foi salvo será perdido. Deseja continuar?')
        with ui.row().classes('justify-end w-full'):
            ui.button('Cancelar', on_click=dialogo_descartar.close).props('flat')
            ui.button(
                'Continuar e descartar',
                on_click=descartar_e_continuar,
                color='negative',
            )

    @ui.refreshable
    def formulario():
        cadastro = atual['cadastro']
        ident = cadastro.identificacao
        editando = atual['editando']

        def ao_mudar_tipo(evento):
            if evento.value == Tipo.TESTE_ESTATICO:
                ident.usa_acionamento = True  # teste estático sempre usa o circuito

        with ui.row().classes('w-full items-center justify-between'):
            ui.label('Cadastro').classes('text-4xl font-bold')
            with ui.row().classes('items-center'):
                if editando:
                    ui.label(f'Editando {ident.codigo}').classes('text-gray-400')
                else:
                    ui.label('Criando um teste novo').classes('text-gray-400')
                ui.button(
                    'Novo teste',
                    icon='add',
                    on_click=lambda: estado.pedir_edicao(None),
                ).props('outline')

        with ui.card().classes('w-full'):
            ui.label('Identificação').classes('text-2xl font-bold')
            with ui.grid(columns=3).classes('w-full'):
                campo_codigo = ui.input('Código do Teste').bind_value(ident, 'codigo').props('outlined')
                campo_tipo = (
                    ui.select(ROTULOS_TIPO, label='Tipo', on_change=ao_mudar_tipo)
                    .bind_value(ident, 'tipo')
                    .props('outlined')
                )
                if editando:
                    # o código é o nome da pasta, e o tipo muda o sentido do registro
                    campo_codigo.props('readonly')
                    campo_tipo.props('readonly')
                ui.input('Projeto').bind_value(ident, 'projeto').props('outlined')
                ui.input('Data', placeholder='DD/MM/AAAA').bind_value(ident, 'data').props('outlined')
                ui.input('Local').bind_value(ident, 'local').props('outlined')
                ui.input('Equipe').bind_value(ident, 'equipe').props('outlined')
                ui.input('Classificação').bind_value(ident, 'classificacao').props('outlined')
                ui.input('Criado por').bind_value(ident, 'criado_por').props('outlined')

            ui.switch('Usa o circuito de acionamento da Beyond').bind_value(
                ident, 'usa_acionamento'
            ).bind_enabled_from(ident, 'tipo', backward=lambda tipo: tipo == Tipo.VOO)

            ui.textarea('Observações').bind_value(ident, 'observacoes').props('outlined').classes('w-full')

        with ui.card().classes('w-full'):
            ui.label('Ficha de Coleta').classes('text-2xl font-bold')
            for parametro in cadastro.ficha:
                _card_parametro(parametro)

        ui.button('Salvar', on_click=gravar)

    formulario()
    estado.ao_mudar_edicao(recarregar)