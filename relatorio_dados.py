import json
from dataclasses import asdict, dataclass, field

from armazenamento import PASTA_TESTES
from graficos import Grafico, Serie


@dataclass
class Calculo:
    id: str
    nome: str  # nome que o usuário dá a este cálculo
    formula: str  # id da fórmula (nome do arquivo em formulas/)
    fonte: str  # id da fonte, ex.: 'sd-001'
    entradas: dict[str, str] = field(default_factory=dict)  # argumento -> coluna original
    parametros: dict[str, float] = field(default_factory=dict)  # só os que o usuário mudou
    observacao: str = ''
    # Registro do último cálculo, para o pacote continuar mostrando o resultado
    # mesmo em um computador sem a fórmula instalada.
    resultado: float | None = None
    unidade: str = ''
    versao: str = ''
    formula_nome: str = ''
    formula_texto: str = ''  # cópia do código, só para consulta (nunca é executada)


@dataclass
class Relatorio:
    graficos: list[Grafico] = field(default_factory=list)
    calculos: list[Calculo] = field(default_factory=list)


def carregar(codigo: str) -> Relatorio:
    caminho = PASTA_TESTES / codigo / 'relatorio.json'
    if not caminho.is_file():
        return Relatorio()
    dados = json.loads(caminho.read_text(encoding='utf-8'))
    return Relatorio(
        graficos=[
            Grafico(**{**g, 'series': [Serie(**s) for s in g['series']]})
            for g in dados.get('graficos', [])
        ],
        calculos=[Calculo(**c) for c in dados.get('calculos', [])],
    )


def salvar(codigo: str, relatorio: Relatorio) -> None:
    pasta = PASTA_TESTES / codigo
    if not (pasta / 'cadastro.json').is_file():
        raise FileNotFoundError(f'A operação {codigo} não existe mais.')
    conteudo = {'schema_version': 2, **asdict(relatorio)}
    temporario = pasta / 'relatorio.json.tmp'
    temporario.write_text(
        json.dumps(conteudo, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    temporario.replace(pasta / 'relatorio.json')  # troca o arquivo de uma vez só