import json

from rocket_station.domain.enums import Axis
from rocket_station.domain.report import Series
from rocket_station.domain.telemetry import (
    X_PACKET,
    X_TIME,
    ExpectedVariable,
    LiveChart,
    TelemetryConfig,
)
from rocket_station.infrastructure.persistence.telemetry_config_repository import (
    FileTelemetryConfigRepository,
)


def test_roundtrip(tmp_path):
    (tmp_path / 'A1').mkdir()
    (tmp_path / 'A1' / 'cadastro.json').write_text('{}', encoding='utf-8')
    repository = FileTelemetryConfigRepository(tmp_path)
    chart = LiveChart('g1', 'T', X_PACKET, None, [Series('a', Axis.RIGHT, '#fff')])
    repository.save('A1', TelemetryConfig([ExpectedVariable('a', 'Alfa', 'm')], [chart]))
    loaded = repository.get('A1')
    assert loaded.charts[0].x == X_PACKET and loaded.charts[0].window_s is None
    assert loaded.charts[0].series[0].axis is Axis.RIGHT and loaded.expected[0].unit == 'm'


def test_reads_legacy_file(tmp_path):
    (tmp_path / 'A1').mkdir()
    legacy = {
        'schema_version': 1,
        'esperadas': [{'nome': 'temperature', 'rotulo': '', 'unidade': ''}],
        'graficos': [{'id': 'g1', 'titulo': 'T', 'x': 'tempo', 'janela_s': 60.0,
                      'series': [{'coluna': 'temperature', 'eixo': 'esquerdo', 'cor': '#5470c6'}]}],
    }
    (tmp_path / 'A1' / 'telemetria.json').write_text(json.dumps(legacy), encoding='utf-8')
    config = FileTelemetryConfigRepository(tmp_path).get('A1')
    assert config.charts[0].x == X_TIME and config.charts[0].window_s == 60.0