"""Fórmulas de cálculo do Relatório.

PARA CRIAR UMA FÓRMULA NOVA: copie `_modelo.py` para um arquivo novo nesta pasta e preencha.
É só isso. Nenhum outro arquivo do projeto precisa ser alterado, porque o app descobre
sozinho tudo o que está nesta pasta. Arquivos que começam com "_" são ignorados.
"""

import importlib
import inspect
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

from .ferramentas import derivada, integral, integral_acumulada, media_inicial  # noqa: F401


class ErroDeFormula(Exception):
    """Erro com mensagem pensada para quem está usando ou escrevendo a fórmula."""


@dataclass
class Formula:
    id: str  # nome do arquivo, ex.: 'valor_maximo'
    nome: str
    descricao: str
    entradas: dict[str, str]  # argumento -> descrição
    parametros: dict[str, tuple[float, str]]  # argumento -> (valor padrão, descrição)
    unidade: str
    usa_tempo: bool
    versao: str
    exemplo: dict | None
    funcao: Callable


_REGISTRO: dict[str, Formula] = {}
_ERROS: dict[str, str] = {}
_carregado = False


def formula(
    *,
    nome: str,
    entradas: dict[str, str],
    descricao: str = '',
    parametros: dict[str, tuple[float, str]] | None = None,
    unidade: str = '',
    usa_tempo: bool = False,
    versao: str = '1',
    exemplo: dict | None = None,
):
    """Decorador que registra uma função como fórmula. Veja `_modelo.py`."""
    parametros = parametros or {}

    def registrar(funcao):
        _validar(funcao, entradas, parametros, usa_tempo)
        _validar_exemplo(exemplo, entradas, parametros, usa_tempo)
        identificador = funcao.__module__.rsplit('.', 1)[-1]
        _REGISTRO[identificador] = Formula(
            id=identificador,
            nome=nome,
            descricao=descricao,
            entradas=dict(entradas),
            parametros=dict(parametros),
            unidade=unidade,
            usa_tempo=usa_tempo,
            versao=versao,
            exemplo=exemplo,
            funcao=funcao,
        )
        return funcao

    return registrar


def _validar(funcao, entradas: dict, parametros: dict, usa_tempo: bool) -> None:
    if not entradas:
        raise ErroDeFormula('Declare ao menos uma entrada em `entradas`.')
    for nome in (*entradas, *parametros):
        if not nome.isidentifier():
            raise ErroDeFormula(f'"{nome}" não é um nome válido de argumento.')
    repetidos = set(entradas) & set(parametros)
    if repetidos:
        raise ErroDeFormula(f'Estes nomes estão em entradas e em parâmetros: {sorted(repetidos)}.')
    for nome, valor in parametros.items():
        valido = (
            isinstance(valor, tuple)
            and len(valor) == 2
            and isinstance(valor[0], (int, float))
            and isinstance(valor[1], str)
        )
        if not valido:
            raise ErroDeFormula(
                f'O parâmetro "{nome}" deve ser declarado assim: '
                f'"{nome}": (valor_padrão, "descrição").'
            )

    esperados = set(entradas) | set(parametros) | ({'dt'} if usa_tempo else set())
    reais = set(inspect.signature(funcao).parameters)
    if esperados != reais:
        partes = []
        if esperados - reais:
            partes.append('faltam os argumentos: ' + ', '.join(sorted(esperados - reais)))
        if reais - esperados:
            partes.append('sobram os argumentos: ' + ', '.join(sorted(reais - esperados)))
        raise ErroDeFormula(
            f'A função "{funcao.__name__}" não bate com o que foi declarado '
            f'({"; ".join(partes)}). Lembre que "dt" só existe com usa_tempo=True.'
        )


def _validar_exemplo(exemplo, entradas: dict, parametros: dict, usa_tempo: bool) -> None:
    if exemplo is None:
        return
    campos = {'entradas', 'parametros', 'taxa_hz', 'esperado'}
    estranhos = set(exemplo) - campos
    if estranhos:
        raise ErroDeFormula(
            f'O `exemplo` tem campos desconhecidos: {sorted(estranhos)}. '
            'Use: entradas, parametros, taxa_hz, esperado.'
        )
    if 'entradas' not in exemplo or 'esperado' not in exemplo:
        raise ErroDeFormula('O `exemplo` precisa ter `entradas` e `esperado`.')
    if set(exemplo['entradas']) != set(entradas):
        raise ErroDeFormula('As entradas do `exemplo` devem ser as mesmas declaradas em `entradas`.')
    desconhecidos = set(exemplo.get('parametros', {})) - set(parametros)
    if desconhecidos:
        raise ErroDeFormula(f'O `exemplo` usa parâmetros que não existem: {sorted(desconhecidos)}.')
    if usa_tempo and not exemplo.get('taxa_hz'):
        raise ErroDeFormula('Esta fórmula usa o tempo: o `exemplo` precisa de `taxa_hz`.')


def carregar_formulas() -> dict[str, Formula]:
    """Descobre e carrega as fórmulas da pasta. Arquivos com problema não derrubam o app."""
    global _carregado
    if not _carregado:
        for arquivo in sorted(Path(__file__).parent.glob('*.py')):
            nome = arquivo.stem
            if nome.startswith('_') or nome == 'ferramentas':
                continue
            try:
                importlib.import_module(f'{__name__}.{nome}')
            except Exception as erro:
                _ERROS[nome] = f'{type(erro).__name__}: {erro}'
        _carregado = True
    return dict(_REGISTRO)


def erros_de_carga() -> dict[str, str]:
    """Arquivos da pasta que não puderam ser carregados, com o motivo."""
    return dict(_ERROS)


def _para_array(valores) -> np.ndarray:
    if isinstance(valores, np.ndarray):
        return valores.astype(float)
    return np.array([np.nan if v is None else v for v in valores], dtype=float)


def executar(
    f: Formula,
    entradas: dict,
    parametros: dict[str, float] | None = None,
    taxa_hz: float | None = None,
) -> float:
    """Roda a fórmula e devolve um número. Levanta ErroDeFormula com mensagem clara."""
    faltando = [nome for nome in f.entradas if nome not in entradas]
    if faltando:
        raise ErroDeFormula('Faltam entradas: ' + ', '.join(faltando) + '.')
    arranjos = {nome: _para_array(entradas[nome]) for nome in f.entradas}
    if len({len(a) for a in arranjos.values()}) != 1:
        raise ErroDeFormula('As entradas têm quantidades de amostras diferentes.')

    kwargs = dict(arranjos)
    if f.usa_tempo:
        if not taxa_hz or taxa_hz <= 0:
            raise ErroDeFormula(
                'Esta fórmula usa o tempo: informe a taxa de amostragem (Hz) da fonte, no Log.'
            )
        kwargs['dt'] = 1.0 / taxa_hz
    valores = parametros or {}
    for nome, (padrao, _) in f.parametros.items():
        kwargs[nome] = float(valores.get(nome, padrao))

    try:
        resultado = f.funcao(**kwargs)
    except Exception as erro:
        texto = str(erro) if isinstance(erro, ValueError) else f'{type(erro).__name__}: {erro}'
        raise ErroDeFormula(f'A fórmula falhou: {texto}') from erro

    try:
        numero = float(resultado)
    except (TypeError, ValueError):
        raise ErroDeFormula('A fórmula deve devolver um único número.') from None
    if not math.isfinite(numero):
        raise ErroDeFormula(
            'O resultado não é um número finito (divisão por zero, ou dados só com lacunas?).'
        )
    return numero