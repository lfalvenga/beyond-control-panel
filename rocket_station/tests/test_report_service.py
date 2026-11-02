import json

import pytest

from src.application.calculation_service import CalculationService
from src.application.operation_service import OperationService
from src.application.report_service import ReportService
from src.application.source_service import SourceService
from src.domain.calculation import Calculation, FormulaInfo, ParameterInfo
from src.domain.enums import Axis
from src.domain.errors import CalculationError
from src.domain.report import Chart, Report
from src.infrastructure.persistence.csv_reader import CsvFileReader
from src.infrastructure.persistence.operation_repository import FileOperationRepository
from src.infrastructure.persistence.report_repository import FileReportRepository
from src.infrastructure.persistence.source_repository import FileSourceRepository

SUM = FormulaInfo(
    'soma', 'Soma', '', {'valores': 'Variável'}, {'fator': ParameterInfo(1.0, 'Fator')}, 'u', False, '1'
)


class FakeCatalog:
    def __init__(self, formulas):
        self._formulas = formulas

    def list(self):
        return self._formulas

    def load_errors(self):
        return {}

    def run(self, formula_id, inputs, parameters, sample_rate_hz):
        if parameters['fator'] < 0:
            raise CalculationError('fator inválido')
        return sum(v for v in inputs['valores'] if v is not None) * parameters['fator']


@pytest.fixture
def env(tmp_path):
    root = tmp_path / 'ops'
    operations = OperationService(FileOperationRepository(root))
    op = operations.new()
    op.code, op.created_by = 'A1', 'Ana'
    operations.create(op)
    sources = SourceService(FileSourceRepository(root), CsvFileReader())
    csv_file = tmp_path / 'log.csv'
    csv_file.write_text('alt;v\n1;2\n3;4\n', encoding='utf-8')
    source = sources.import_csv('A1', csv_file, {}, 10)
    reports = ReportService(FileReportRepository(root), sources)
    calculations = CalculationService(FakeCatalog({'soma': SUM}), sources)
    return reports, calculations, source, root


def test_chart_by_sample(env):
    reports, _, source, _ = env
    data = reports.chart_data('A1', Chart.new(source.id, 'alt'))
    assert data.x_label == 'Amostra' and data.series[0].points == [[1, 1.0], [2, 3.0]]


def test_chart_by_time_uses_the_sample_rate(env):
    reports, _, source, _ = env
    chart = Chart.new(source.id, 'alt')
    chart.x = 'time'
    data = reports.chart_data('A1', chart)
    assert data.x_label == 'Tempo (s)' and data.series[0].points == [[0.0, 1.0], [0.1, 3.0]]


def test_chart_without_series_explains_why(env):
    reports, _, source, _ = env
    assert 'Adicione' in reports.chart_data('A1', Chart.new(source.id)).message


def test_report_roundtrip(env):
    reports, _, source, _ = env
    report = Report(charts=[Chart.new(source.id, 'alt')])
    report.charts[0].series[0].axis = Axis.RIGHT
    reports.save('A1', report)
    loaded = reports.load('A1')
    assert loaded.charts[0].series[0].axis is Axis.RIGHT and loaded.charts[0].x == 'sample'


def test_reads_legacy_report_file(env):
    reports, _, _, root = env
    legacy = {
        'schema_version': 2,
        'graficos': [{'id': 'g1', 'titulo': 'T', 'fonte': 'sd-001', 'x': 'tempo',
                      'series': [{'coluna': 'alt', 'eixo': 'direito', 'cor': '#ee6666'}]}],
        'calculos': [],
    }
    (root / 'A1' / 'relatorio.json').write_text(json.dumps(legacy), encoding='utf-8')
    chart = reports.load('A1').charts[0]
    assert chart.x == 'time' and chart.series[0].axis is Axis.RIGHT and chart.notes == ''


def test_calculation_success_updates_the_record(env):
    _, calculations, source, _ = env
    calc = Calculation.new(SUM, source.id)
    calc.inputs = {'valores': 'alt'}
    calc.parameters = {'fator': 2}
    evaluation = calculations.evaluate('A1', calc)
    assert evaluation.value == 8.0 and calc.result == 8.0 and calc.unit == 'u'


def test_calculation_requires_the_inputs(env):
    _, calculations, source, _ = env
    calc = Calculation.new(SUM, source.id)
    calc.result = 99.0  # resultado antigo não pode sobreviver a um cálculo sem entradas
    assert 'Escolha' in calculations.evaluate('A1', calc).error and calc.result is None


def test_calculation_with_missing_formula_keeps_the_saved_result(env):
    _, calculations, source, _ = env
    calc = Calculation('c1', 'x', 'sumiu', source.id, result=5.0, unit='N')
    evaluation = calculations.evaluate('A1', calc)
    assert evaluation.installed is False and calc.result == 5.0


def test_calculation_error_clears_the_result(env):
    _, calculations, source, _ = env
    calc = Calculation.new(SUM, source.id)
    calc.inputs = {'valores': 'alt'}
    calc.parameters = {'fator': -1}
    assert calculations.evaluate('A1', calc).error == 'fator inválido' and calc.result is None