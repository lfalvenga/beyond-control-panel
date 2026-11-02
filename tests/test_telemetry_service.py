import pytest

from src.application.recording_service import RecordingService
from src.application.telemetry_service import TelemetryService
from src.domain.enums import SourceKind
from src.domain.errors import ValidationError
from src.domain.telemetry import ExpectedVariable, TelemetryConfig
from src.infrastructure.persistence.source_repository import FileSourceRepository
from src.infrastructure.telemetry.recorder import FileRecordingStorage


class FakeStation:
    def __init__(self):
        self.is_open = False
        self.lines = []
        self.written = []

    def list_ports(self):
        return [('COM9', 'falsa')]

    def open(self, port, baud):
        self.is_open = True

    def close(self):
        self.is_open = False

    def read_lines(self):
        lines, self.lines = self.lines, []
        return lines

    def take_error(self):
        return ''

    def write_line(self, text):
        self.written.append(text)


@pytest.fixture
def env(tmp_path):
    clock = {'now': 100.0}
    station = FakeStation()
    telemetry = TelemetryService(station, clock=lambda: clock['now'])
    sources = FileSourceRepository(tmp_path)
    recording = RecordingService(FileRecordingStorage(tmp_path), sources, clock=lambda: clock['now'])
    telemetry.subscribe(recording.on_packet)
    return telemetry, recording, station, sources, clock, tmp_path


def test_new_variables_are_discovered_and_invalid_lines_counted(env):
    telemetry, _, station, *_ = env
    telemetry.connect('COM9')
    station.lines = ['{"a":1}', '{"a":2,"b":3}', 'lixo']
    telemetry.poll()
    assert set(telemetry.variables) == {'a', 'b'} and telemetry.link.invalid == 1


def test_ack_changes_are_reported_once(env):
    telemetry, _, station, *_ = env
    telemetry.connect('COM9')
    station.lines = ['{"ack1":0}', '{"ack1":1}', '{"ack1":1}', '{"ack1":0}']
    telemetry.poll()
    assert telemetry.ack_changes == [(1, 0, 1), (1, 1, 0)]


def test_send_requires_connection_and_writes_compact_json(env):
    telemetry, _, station, *_ = env
    with pytest.raises(ConnectionError):
        telemetry.send({'cmd1': 1})
    telemetry.connect('COM9')
    telemetry.send({'cmd1': 1})
    assert station.written == ['{"cmd1":1}']


def test_recording_creates_raw_file_and_radio_source(env):
    telemetry, recording, station, sources, clock, tmp = env
    telemetry.connect('COM9')
    recording.start('A1')
    for i in range(3):
        clock['now'] += 0.5
        station.lines = [f'{{"packetN":{i},"a":{i}}}']
        telemetry.poll()
    source = recording.finish_active(TelemetryConfig([ExpectedVariable('a', 'Alfa', 'm')], []))
    assert source.kind is SourceKind.RADIO and source.rows == 3
    assert source.sample_rate_hz == pytest.approx(2.0)
    assert [c.display for c in source.columns] == ['Tempo (s)', 'Nº do pacote', 'Alfa (m)']
    assert (tmp / 'A1' / 'dados' / 'radio-001.csv').exists()
    assert sources.list_all('A1')[0].id == 'radio-001'


def test_interrupted_recording_is_pending_and_can_be_finalized(env):
    telemetry, recording, station, _, clock, _ = env
    telemetry.connect('COM9')
    recording.start('A1')
    station.lines = ['{"a":1}', '{"a":2}']
    clock['now'] += 1
    telemetry.poll()
    recording.stop()  # simula a queda: nada foi finalizado
    assert recording.pending('A1') == ['radio-001']
    recording.finalize('A1', 'radio-001', TelemetryConfig())
    assert recording.pending('A1') == []


def test_empty_recording_cannot_be_finalized(env):
    _, recording, *_ = env
    recording.start('A1')
    with pytest.raises(ValidationError):
        recording.finish_active(TelemetryConfig())