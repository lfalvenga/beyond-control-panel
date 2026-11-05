from pathlib import Path

from src.domain.calculation import Calculation
from src.domain.enums import Axis
from src.domain.errors import OperationNotFoundError
from src.domain.report import Chart, Report, Series
from src.infrastructure.persistence.file_storage import read_json, write_json_atomic
from src.infrastructure.persistence.operation_repository import (
    FILE_NAME as OPERATION_FILE,
)

FILE_NAME = 'relatorio.json'  # nomes e chaves históricos, mantidos por compatibilidade
REPORT_FORMAT_VERSION = 2

_AXIS_TO_JSON = {Axis.LEFT: 'esquerdo', Axis.RIGHT: 'direito'}
_AXIS_FROM_JSON = {v: k for k, v in _AXIS_TO_JSON.items()}
_X_TO_JSON = {'sample': 'amostra', 'time': 'tempo'}
_X_FROM_JSON = {v: k for k, v in _X_TO_JSON.items()}


def _chart_to_json(c: Chart) -> dict:
    return {
        'id': c.id,
        'titulo': c.title,
        'fonte': c.source_id,
        'x': _X_TO_JSON.get(c.x, c.x),
        'series': [
            {'coluna': s.column, 'eixo': _AXIS_TO_JSON[s.axis], 'cor': s.color} for s in c.series
        ],
        'observacao': c.notes,
    }


def _chart_from_json(d: dict) -> Chart:
    return Chart(
        id=d['id'],
        title=d['titulo'],
        source_id=d['fonte'],
        x=_X_FROM_JSON.get(d.get('x', 'amostra'), d.get('x', 'amostra')),
        series=[
            Series(s['coluna'], _AXIS_FROM_JSON[s.get('eixo', 'esquerdo')], s.get('cor', '#5470c6'))
            for s in d.get('series', [])
        ],
        notes=d.get('observacao', ''),
    )


def _calculation_to_json(c: Calculation) -> dict:
    return {
        'id': c.id,
        'nome': c.name,
        'formula': c.formula_id,
        'fonte': c.source_id,
        'entradas': c.inputs,
        'parametros': c.parameters,
        'vinculos': c.links,
        'observacao': c.notes,
        'resultado': c.result,
        'unidade': c.unit,
        'versao': c.version,
        'formula_nome': c.formula_name,
        'formula_texto': c.formula_text,
    }


def _calculation_from_json(d: dict) -> Calculation:
    return Calculation(
        id=d['id'],
        name=d['nome'],
        formula_id=d['formula'],
        source_id=d['fonte'],
        inputs=dict(d.get('entradas', {})),
        parameters=dict(d.get('parametros', {})),
        links=dict(d.get('vinculos', {})),
        notes=d.get('observacao', ''),
        result=d.get('resultado'),
        unit=d.get('unidade', ''),
        version=d.get('versao', ''),
        formula_name=d.get('formula_nome', ''),
        formula_text=d.get('formula_texto', ''),
    )


class FileReportRepository:
    def __init__(self, root: Path) -> None:
        self._root = root

    def get(self, code: str) -> Report:
        file = self._root / code / FILE_NAME
        if not file.is_file():
            return Report()
        data = read_json(file)
        return Report(
            charts=[_chart_from_json(c) for c in data.get('graficos', [])],
            calculations=[_calculation_from_json(c) for c in data.get('calculos', [])],
        )

    def save(self, code: str, report: Report) -> None:
        folder = self._root / code
        if not (folder / OPERATION_FILE).is_file():
            raise OperationNotFoundError(f'A operação {code} não existe mais.')
        write_json_atomic(
            folder / FILE_NAME,
            {
                'schema_version': REPORT_FORMAT_VERSION,
                'graficos': [_chart_to_json(c) for c in report.charts],
                'calculos': [_calculation_to_json(c) for c in report.calculations],
            },
        )