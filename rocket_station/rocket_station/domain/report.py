import uuid
from dataclasses import dataclass, field

from rocket_station.domain.calculation import Calculation
from rocket_station.domain.enums import Axis

PALETTE = [
    '#5470c6', '#ee6666', '#91cc75', '#fac858', '#73c0de',
    '#3ba272', '#fc8452', '#9a60b4', '#ea7ccc',
]


@dataclass
class Series:
    column: str  # nome ORIGINAL da coluna (continua valendo se o usuário renomear)
    axis: Axis = Axis.LEFT
    color: str = PALETTE[0]


@dataclass
class Chart:
    id: str
    title: str
    source_id: str
    x: str = 'sample'  # 'sample', 'time' ou o nome original de uma coluna
    series: list[Series] = field(default_factory=list)
    notes: str = ''

    @classmethod
    def new(cls, source_id: str, first_column: str | None = None) -> 'Chart':
        series = [Series(first_column)] if first_column else []
        return cls(
            id=uuid.uuid4().hex[:8], title='Novo gráfico', source_id=source_id, series=series
        )


@dataclass
class Report:
    charts: list[Chart] = field(default_factory=list)
    calculations: list[Calculation] = field(default_factory=list)