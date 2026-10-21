from dataclasses import dataclass, field
from enum import Enum

SCHEMA_VERSION = 3


class Parecer(str, Enum):
    PENDENTE = 'Pendente'
    DEFERIDO = 'Deferido'
    INDEFERIDO = 'Indeferido'
    NAO_SE_APLICA = 'Não se aplica'


class Tipo(str, Enum):
    TESTE_ESTATICO = 'teste_estatico'
    VOO = 'voo'


ROTULOS_TIPO = {
    Tipo.TESTE_ESTATICO: 'Teste estático',
    Tipo.VOO: 'Voo',
}


@dataclass
class Identificacao:
    codigo: str = ''
    tipo: Tipo = Tipo.TESTE_ESTATICO
    usa_acionamento: bool = True
    projeto: str = ''
    data: str = ''
    local: str = ''
    equipe: str = ''
    criado_por: str = ''
    classificacao: str = ''
    observacoes: str = ''


@dataclass
class Parametro:
    nome: str
    unidade: str = ''
    valor: float | None = None
    responsavel: str = ''
    horario: str = ''
    parecer: Parecer = Parecer.PENDENTE


# (nome, unidade padrão), na ordem em que aparecem na ficha
PARAMETROS_INICIAIS = [
    ('Pressão Atmosférica', 'Pa'),
    ('Latitude', '°'),
    ('Longitude', '°'),
    ('Altitude', 'm'),
    ('Inclinação', '°'),
    ('Azimute', '°'),
]


def nova_ficha() -> list[Parametro]:
    return [Parametro(nome=n, unidade=u) for n, u in PARAMETROS_INICIAIS]


@dataclass
class Cadastro:
    schema_version: int = SCHEMA_VERSION
    id: str = ''
    identificacao: Identificacao = field(default_factory=Identificacao)
    ficha: list[Parametro] = field(default_factory=list)