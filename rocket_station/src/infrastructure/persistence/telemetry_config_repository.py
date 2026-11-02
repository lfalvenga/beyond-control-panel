from pathlib import Path

from src.domain.enums import Axis
from src.domain.errors import OperationNotFoundError
from src.domain.report import Series
from src.domain.telemetry import (
    X_PACKET,
    X_TIME,
    ExpectedVariable,
    LiveChart,
    TelemetryConfig,
)
from src.infrastructure.persistence.file_storage import read_json, write_json_atomic
from src.infrastructure.persistence.operation_repository import (
    FILE_NAME as OPERATION_FILE,
)

FILE_NAME = 'telemetria.json'  # nomes e chaves históricos, mantidos por compatibilidade
_AXIS_TO_JSON = {Axis.LEFT: 'esquerdo', Axis.RIGHT: 'direito'}
_AXIS_FROM_JSON = {v: k for k, v in _AXIS_TO_JSON.items()}
_X_TO_JSON = {X_TIME: 'tempo', X_PACKET: 'seq'}
_X_FROM_JSON = {v: k for k, v in _X_TO_JSON.items()}


class FileTelemetryConfigRepository:
    def __init__(self, root: Path) -> None:
        self._root = root

    def get(self, code: str) -> TelemetryConfig:
        file = self._root / code / FILE_NAME
        if not file.is_file():
            return TelemetryConfig()
        data = read_json(file)
        return TelemetryConfig(
            expected=[
                ExpectedVariable(e['nome'], e.get('rotulo', ''), e.get('unidade', ''))
                for e in data.get('esperadas', [])
            ],
            charts=[
                LiveChart(
                    id=g['id'],
                    title=g.get('titulo', 'Novo gráfico'),
                    x=_X_FROM_JSON.get(g.get('x', 'tempo'), g.get('x', 'tempo')),
                    window_s=g.get('janela_s'),
                    series=[
                        Series(s['coluna'], _AXIS_FROM_JSON[s.get('eixo', 'esquerdo')], s.get('cor', '#5470c6'))
                        for s in g.get('series', [])
                    ],
                )
                for g in data.get('graficos', [])
            ],
        )

    def save(self, code: str, config: TelemetryConfig) -> None:
        folder = self._root / code
        if not (folder / OPERATION_FILE).is_file():
            raise OperationNotFoundError(f'A operação {code} não existe mais.')
        write_json_atomic(
            folder / FILE_NAME,
            {
                'schema_version': 1,
                'esperadas': [
                    {'nome': e.name, 'rotulo': e.label, 'unidade': e.unit} for e in config.expected
                ],
                'graficos': [
                    {
                        'id': c.id,
                        'titulo': c.title,
                        'x': _X_TO_JSON.get(c.x, c.x),
                        'janela_s': c.window_s,
                        'series': [
                            {'coluna': s.column, 'eixo': _AXIS_TO_JSON[s.axis], 'cor': s.color}
                            for s in c.series
                        ],
                    }
                    for c in config.charts
                ],
            },
        )