import json
from dataclasses import asdict, dataclass, field
from uuid import uuid4

from armazenamento import PASTA_TESTES
from graficos import Serie


@dataclass
class Esperada:
    nome: str  # exatamente como a estação envia
    rotulo: str = ''  # nome de exibição (opcional)
    unidade: str = ''  # opcional


@dataclass
class GraficoVivo:
    id: str
    titulo: str = 'Novo gráfico'
    x: str = 'tempo'  # 'tempo' (s), 'seq' (número do pacote) ou o nome de uma variável
    janela_s: float | None = 60.0  # só os últimos N segundos; None = tudo
    series: list[Serie] = field(default_factory=list)


@dataclass
class Telemetria:
    esperadas: list[Esperada] = field(default_factory=list)
    graficos: list[GraficoVivo] = field(default_factory=list)


def novo_grafico() -> GraficoVivo:
    return GraficoVivo(id=uuid4().hex[:8])


def carregar(codigo: str) -> Telemetria:
    caminho = PASTA_TESTES / codigo / 'telemetria.json'
    if not caminho.is_file():
        return Telemetria()
    dados = json.loads(caminho.read_text(encoding='utf-8'))
    return Telemetria(
        esperadas=[Esperada(**e) for e in dados.get('esperadas', [])],
        graficos=[
            GraficoVivo(**{**g, 'series': [Serie(**s) for s in g['series']]})
            for g in dados.get('graficos', [])
        ],
    )


def salvar(codigo: str, tel: Telemetria) -> None:
    pasta = PASTA_TESTES / codigo
    if not (pasta / 'cadastro.json').is_file():
        raise FileNotFoundError(f'A operação {codigo} não existe mais.')
    conteudo = {'schema_version': 1, **asdict(tel)}
    temporario = pasta / 'telemetria.json.tmp'
    temporario.write_text(
        json.dumps(conteudo, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    temporario.replace(pasta / 'telemetria.json')  # troca o arquivo de uma vez só