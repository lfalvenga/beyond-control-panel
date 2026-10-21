from dataclasses import dataclass, field

from rocket_station.application.ports import ReportRepository
from rocket_station.application.source_service import SourceService
from rocket_station.domain.enums import Axis
from rocket_station.domain.errors import ValidationError
from rocket_station.domain.report import Chart, Report


@dataclass
class SeriesData:
    name: str
    axis: Axis
    color: str
    points: list[list[float | None]]


@dataclass
class ChartData:
    message: str = ''  # preenchida quando não dá para desenhar
    x_label: str = ''
    series: list[SeriesData] = field(default_factory=list)
    ordered: bool = True  # x crescente: permite reduzir a densidade na exibição


class ReportService:
    def __init__(self, repository: ReportRepository, sources: SourceService) -> None:
        self._repository = repository
        self._sources = sources

    def load(self, code: str) -> Report:
        return self._repository.get(code)

    def save(self, code: str, report: Report) -> None:
        self._repository.save(code, report)

    def new_chart(self, code: str) -> Chart:
        sources = self._sources.list_all(code)
        if not sources:
            raise ValidationError('Importe um CSV na tela Log para montar gráficos.')
        source = sources[-1]  # a importada por último
        try:
            first = next(iter(self._sources.numeric_columns(code, source)), None)
        except (OSError, ValueError):
            first = None
        return Chart.new(source.id, first)

    def chart_data(self, code: str, chart: Chart) -> ChartData:
        source = next((s for s in self._sources.list_all(code) if s.id == chart.source_id), None)
        if source is None:
            return ChartData(message='A fonte deste gráfico não existe mais. Escolha outra.')
        try:
            numeric = self._sources.numeric_columns(code, source)
        except (OSError, ValueError):
            numeric = {}
        if not numeric:
            return ChartData(message='Esta fonte não tem colunas numéricas (ou não foi possível lê-la).')
        valid = [s for s in chart.series if s.column in numeric]
        if not valid:
            return ChartData(message='Adicione ao menos uma variável para o eixo Y.')

        names = {c.original: c.display for c in source.columns}
        total = len(next(iter(numeric.values())))
        rate = source.sample_rate_hz
        if chart.x == 'time' and rate:
            xs, x_label, ordered = [i / rate for i in range(total)], 'Tempo (s)', True
        elif chart.x in numeric:
            xs, x_label, ordered = numeric[chart.x], names.get(chart.x, chart.x), False
        else:
            xs, x_label, ordered = list(range(1, total + 1)), 'Amostra', True
        series = [
            SeriesData(
                name=names.get(s.column, s.column),
                axis=s.axis,
                color=s.color,
                points=[[x, y] for x, y in zip(xs, numeric[s.column]) if x is not None],
            )
            for s in valid
        ]
        return ChartData(x_label=x_label, series=series, ordered=ordered)