import math
from dataclasses import dataclass, field

from src.domain.enums import SourceKind
from src.domain.errors import ValidationError


@dataclass
class Column:
    original: str  # como está no cabeçalho do CSV
    display: str  # como o usuário quer ver


@dataclass
class DataSource:
    id: str
    file: str
    origin: str
    imported_at: str
    separator: str
    encoding: str
    rows: int
    columns: list[Column] = field(default_factory=list)
    sample_rate_hz: float | None = None
    kind: SourceKind = SourceKind.SD


@dataclass
class CsvPreview:
    columns: list[str]
    rows: list[list[str]]  # só as primeiras
    total_rows: int
    separator: str
    encoding: str


def validate_sample_rate(rate: float | None) -> float | None:
    if rate is None:
        return None
    if not math.isfinite(rate) or rate <= 0:
        raise ValidationError('A taxa de amostragem deve ser um número maior que zero.')
    return float(rate)


def validate_columns(columns: list[Column]) -> None:
    names = [c.display for c in columns]
    if any(not n for n in names):
        raise ValidationError('Nenhum nome pode ficar vazio.')
    if len({n.lower() for n in names}) != len(names):
        raise ValidationError('Os nomes das variáveis devem ser diferentes entre si.')