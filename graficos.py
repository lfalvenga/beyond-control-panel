import json
from dataclasses import asdict, dataclass, field
from uuid import uuid4

from armazenamento import PASTA_TESTES

PALETA = [
    '#5470c6', '#ee6666', '#91cc75', '#fac858', '#73c0de',
    '#3ba272', '#fc8452', '#9a60b4', '#ea7ccc',
]


@dataclass
class Serie:
    coluna: str  # nome ORIGINAL da coluna no CSV (continua valendo se o usuário renomear)
    eixo: str = 'esquerdo'  # 'esquerdo' ou 'direito'
    cor: str = '#5470c6'


@dataclass
class Grafico:
    id: str
    titulo: str
    fonte: str  # id da fonte, ex.: 'sd-001'
    x: str = 'amostra'  # 'amostra' ou o nome original de uma coluna
    series: list[Serie] = field(default_factory=list)
    observacao: str = ''


def listar_graficos(codigo: str) -> list[Grafico]:
    caminho = PASTA_TESTES / codigo / 'relatorio.json'
    if not caminho.is_file():
        return []
    dados = json.loads(caminho.read_text(encoding='utf-8'))
    return [
        Grafico(**{**g, 'series': [Serie(**s) for s in g['series']]})
        for g in dados['graficos']
    ]


def salvar_graficos(codigo: str, graficos: list[Grafico]) -> None:
    pasta = PASTA_TESTES / codigo
    if not (pasta / 'cadastro.json').is_file():
        raise FileNotFoundError(f'A operação {codigo} não existe mais.')
    conteudo = {'schema_version': 1, 'graficos': [asdict(g) for g in graficos]}
    temporario = pasta / 'relatorio.json.tmp'
    temporario.write_text(
        json.dumps(conteudo, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    temporario.replace(pasta / 'relatorio.json')  # troca o arquivo de uma vez só


def novo_grafico(fonte_id: str, primeira_coluna: str | None = None) -> Grafico:
    series = [Serie(coluna=primeira_coluna, cor=PALETA[0])] if primeira_coluna else []
    return Grafico(id=uuid4().hex[:8], titulo='Novo gráfico', fonte=fonte_id, series=series)