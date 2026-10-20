from uuid import uuid4

import formulas
import fontes
import relatorio_dados
from nicegui import ui


def _ao_mudar(objeto, atributo: str, depois):
    """Devolve um tratador que grava o novo valor no objeto e chama `depois`."""

    def tratador(evento):
        setattr(objeto, atributo, evento.value)
        depois()

    return tratador


def _numeros_da_fonte(codigo: str, fonte) -> dict:
    if fonte is None:
        return {}
    try:
        return fontes.carregar_numeros(codigo, fonte)
    except (OSError, ValueError):
        return {}



def novo_calculo(disponiveis: dict, fonte_id: str) -> relatorio_dados.Calculo:
    f = next(iter(disponiveis.values()))
    return relatorio_dados.Calculo(
        id=uuid4().hex[:8],
        nome=f.nome,
        formula=f.id,
        fonte=fonte_id,
        unidade=f.unidade,
        versao=f.versao,
        formula_nome=f.nome,
    )


def _calcular(codigo, c, disponiveis, por_id):
    """Devolve (valor, erro, instalada). Nunca levanta exceção."""
    f = disponiveis.get(c.formula)
    if f is None:
        return None, None, False
    fonte = por_id.get(c.fonte)
    if fonte is None:
        return None, 'A fonte deste cálculo não existe mais. Escolha outra.', True
    numeros = _numeros_da_fonte(codigo, fonte)
    entradas = {}
    for argumento, descricao in f.entradas.items():
        coluna = c.entradas.get(argumento)
        if not coluna or coluna not in numeros:
            return None, f'Escolha a variável de "{descricao}".', True
        entradas[argumento] = numeros[coluna]
    parametros = {
        nome: padrao if c.parametros.get(nome) is None else c.parametros[nome]
        for nome, (padrao, _) in f.parametros.items()
    }
    try:
        valor = formulas.executar(f, entradas, parametros, fonte.taxa_hz)
    except formulas.ErroDeFormula as erro:
        return None, str(erro), True
    return valor, None, True


def card_calculo(codigo, c, todas_fontes, disponiveis, ao_mudar, remover) -> None:
    por_id = {f.id: f for f in todas_fontes}

    def recalcular():
        """Recalcula e atualiza o registro do cálculo (que só vai ao pacote ao salvar)."""
        valor, erro, instalada = _calcular(codigo, c, disponiveis, por_id)
        f = disponiveis.get(c.formula)
        if instalada:
            c.resultado = valor
            if valor is not None:
                c.unidade = f.unidade
                c.formula_nome = f.nome
                c.versao = f.versao
        return valor, erro, instalada

    ultimo = {'v': recalcular()}

    def atualizar_resultado():
        ultimo['v'] = recalcular()
        resultado.refresh()
        ao_mudar()

    def trocar_formula(evento):
        antiga = disponiveis.get(c.formula)
        nova = disponiveis.get(evento.value)
        if antiga is not None and nova is not None and c.nome == antiga.nome:
            c.nome = nova.nome  # o nome só acompanha se o usuário não tinha mudado
        c.formula = evento.value
        c.entradas = {}
        c.parametros = {}
        controles.refresh()
        atualizar_resultado()

    def trocar_fonte(evento):
        c.fonte = evento.value
        numeros = _numeros_da_fonte(codigo, por_id.get(c.fonte))
        c.entradas = {a: col for a, col in c.entradas.items() if col in numeros}
        controles.refresh()
        atualizar_resultado()

    def mudar_entrada(argumento):
        def tratador(evento):
            c.entradas[argumento] = evento.value
            atualizar_resultado()

        return tratador

    def mudar_parametro(nome):
        def tratador(evento):
            if evento.value is None:
                c.parametros.pop(nome, None)  # campo vazio: volta ao padrão
            else:
                c.parametros[nome] = evento.value
            atualizar_resultado()

        return tratador

    @ui.refreshable
    def controles():
        f = disponiveis.get(c.formula)
        fonte = por_id.get(c.fonte)
        numeros = _numeros_da_fonte(codigo, fonte)
        nomes = {col.original: col.exibicao for col in fonte.colunas} if fonte else {}
        variaveis = {col: nomes.get(col, col) for col in numeros}

        opcoes_formula = {fid: fo.nome for fid, fo in disponiveis.items()}
        if c.formula not in opcoes_formula:
            opcoes_formula[c.formula] = f'{c.formula_nome or c.formula} (não instalada)'
        opcoes_fonte = {fo.id: f'{fo.id} · {fo.origem}' for fo in todas_fontes}
        if c.fonte not in opcoes_fonte:
            opcoes_fonte[c.fonte] = f'{c.fonte} (indisponível)'

        with ui.row().classes('w-full items-end'):
            ui.select(
                opcoes_formula, label='Fórmula', value=c.formula, on_change=trocar_formula
            ).props('outlined dense').classes('w-72')
            ui.select(
                opcoes_fonte, label='Fonte', value=c.fonte, on_change=trocar_fonte
            ).props('outlined dense').classes('w-64')

        if f is None:
            return
        if f.descricao:
            ui.label(f.descricao).classes('text-gray-400')
        with ui.row().classes('w-full items-end'):
            for argumento, descricao in f.entradas.items():
                atual = c.entradas.get(argumento)
                opcoes_var = dict(variaveis)
                if atual and atual not in opcoes_var:
                    opcoes_var[atual] = f'{atual} (indisponível)'
                ui.select(
                    opcoes_var, label=descricao, value=atual, on_change=mudar_entrada(argumento)
                ).props('outlined dense').classes('w-64')
        if f.parametros:
            with ui.row().classes('w-full items-end'):
                for nome, (padrao, descricao) in f.parametros.items():
                    valor = c.parametros.get(nome)
                    ui.number(
                        descricao,
                        value=padrao if valor is None else valor,
                        on_change=mudar_parametro(nome),
                    ).props('outlined dense debounce=300').classes('w-64')
        if f.usa_tempo and fonte is not None and not fonte.taxa_hz:
            ui.label(
                'Esta fórmula usa o tempo: informe a taxa de amostragem desta fonte, no Log.'
            ).classes('text-orange-400')

    @ui.refreshable
    def resultado():
        valor, erro, instalada = ultimo['v']
        with ui.card().classes('w-full').props('flat bordered'):
            if not instalada:
                ui.label(f'A fórmula "{c.formula}" não está instalada neste computador.').classes(
                    'text-orange-400'
                )
                if c.resultado is not None:
                    ui.label(
                        f'Último resultado salvo: {c.resultado:.6g} {c.unidade} '
                        f'(fórmula "{c.formula_nome}")'
                    )
            elif erro:
                ui.label(erro).classes('text-orange-400')
            else:
                ui.label(f'{valor:.6g} {c.unidade}'.strip()).classes('text-3xl font-bold')

    with ui.card().classes('w-full'):
        with ui.row().classes('w-full items-center justify-between'):
            ui.input(
                'Nome do cálculo', value=c.nome, on_change=_ao_mudar(c, 'nome', ao_mudar)
            ).bind_value_from(c, 'nome').props('outlined dense debounce=500').classes('grow')
            ui.button(
                'Remover cálculo', icon='delete', on_click=lambda: remover(c)
            ).props('flat color=negative')
        controles()
        resultado()
        ui.textarea(
            'Observações', value=c.observacao, on_change=_ao_mudar(c, 'observacao', ao_mudar)
        ).props('outlined autogrow debounce=500').classes('w-full')