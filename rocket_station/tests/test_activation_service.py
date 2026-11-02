import json

import pytest

from src.application.activation_service import ActivationService
from src.application.recording_service import RecordingService
from src.application.telemetry_service import TelemetryService
from src.domain.activation import COUNTDOWN_S
from src.infrastructure.persistence.source_repository import FileSourceRepository
from src.infrastructure.telemetry.recorder import FileRecordingStorage

ALL_ACKS = '{"ack1":1,"ack2":1,"ack3":1}'


class FakeStation:
    def __init__(self):
        self.is_open = False
        self.lines = []
        self.written = []
        self.fail_writes = False

    def list_ports(self):
        return []

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
        if self.fail_writes:
            raise ConnectionError('Falha ao enviar: porta fechada')
        self.written.append(text)


class MemoryLog:
    def __init__(self):
        self.events = []

    def append(self, code, event):
        self.events.append((code, event))

    def read(self, code):
        return [e for c, e in self.events if c == code]


@pytest.fixture
def env(tmp_path):
    clock = {'now': 100.0}
    now = lambda: clock['now']  # noqa: E731
    station = FakeStation()
    telemetry = TelemetryService(station, clock=now)
    recording = RecordingService(
        FileRecordingStorage(tmp_path), FileSourceRepository(tmp_path), clock=now
    )
    telemetry.subscribe(recording.on_packet)
    log = MemoryLog()
    service = ActivationService(telemetry, recording, log, clock=now)
    telemetry.connect('COM9')
    return service, telemetry, recording, station, log, clock


def feed(telemetry, station, line):
    station.lines = [line]
    telemetry.poll()


def arm_all(env):
    service, telemetry, _, station, _, _ = env
    acks = {}
    for n in (1, 2, 3):
        service.arm('A1', n)
        acks[f'ack{n}'] = 1
        feed(telemetry, station, json.dumps(acks))
        service.tick('A1', True)


def kinds(log):
    return [e['evento'] for _, e in log.events]


def test_arming_follows_the_order(env):
    service, _, _, station, *_ = env
    notices = service.arm('A1', 2)  # o 1 ainda não está confirmado
    assert station.written == [] and notices[0].level == 'warning'
    service.arm('A1', 1)
    assert station.written == ['{"cmd1":1}']


def test_stage_3_starts_the_recording_before_sending(env):
    _, _, recording, station, log, _ = env
    arm_all(env)
    assert recording.recording and station.written[-1] == '{"cmd3":1}'
    events = [e for _, e in log.events]
    start = next(i for i, e in enumerate(events) if e['evento'] == 'gravacao_iniciada')
    cmd3 = next(i for i, e in enumerate(events) if e['evento'] == 'cmd' and e['estagio'] == 3)
    assert start < cmd3


def test_stage_3_is_not_armed_if_the_recording_cannot_open(env, monkeypatch):
    service, telemetry, recording, station, _, _ = env
    feed(telemetry, station, '{"ack1":1,"ack2":1}')

    def boom(*args):
        raise OSError('disco cheio')

    monkeypatch.setattr(recording._storage, 'open_raw', boom)
    notices = service.arm('A1', 3)
    assert notices[0].level == 'negative' and station.written == [] and not recording.recording


def test_ignition_sends_cmd4_once_after_the_countdown(env):
    service, telemetry, _, station, _, clock = env
    arm_all(env)
    service.start_countdown('A1', True)
    assert service.view('A1', True).counting
    clock['now'] += COUNTDOWN_S - 0.5  # ainda dentro do tempo
    feed(telemetry, station, ALL_ACKS)
    service.tick('A1', True)
    assert '{"cmd4":1}' not in station.written
    clock['now'] += 1.0
    feed(telemetry, station, ALL_ACKS)
    service.tick('A1', True)
    service.tick('A1', True)
    assert station.written.count('{"cmd4":1}') == 1
    assert service.view('A1', True).ignition_sent_at
    service.start_countdown('A1', True)  # uma segunda ignição não começa
    assert not service.view('A1', True).counting


def test_countdown_aborts_and_never_sends_if_the_link_goes_silent(env):
    service, _, _, station, log, clock = env
    arm_all(env)
    service.start_countdown('A1', True)
    clock['now'] += 4.0  # nenhum pacote chegou: o link está mudo
    service.tick('A1', True)
    clock['now'] += 10.0
    service.tick('A1', True)
    assert '{"cmd4":1}' not in station.written and 'contagem_cancelada' in kinds(log)


def test_countdown_aborts_if_a_stage_ack_regresses(env):
    service, telemetry, _, station, _, _ = env
    arm_all(env)
    service.start_countdown('A1', True)
    feed(telemetry, station, '{"ack3":0}')
    notices = service.tick('A1', True)
    assert not service.view('A1', True).counting
    assert any(n.persistent for n in notices) and '{"cmd4":1}' not in station.written


def test_t0_is_logged_only_on_the_first_ack3(env):
    service, telemetry, _, station, log, _ = env
    arm_all(env)
    feed(telemetry, station, '{"ack3":0}')
    service.tick('A1', True)
    feed(telemetry, station, '{"ack3":1}')
    service.tick('A1', True)
    assert kinds(log).count('t0') == 1


def test_disarm_sends_in_reverse_order(env):
    service, *_, station, _, _ = env
    arm_all(env)
    service.disarm('A1')
    assert station.written[-3:] == ['{"cmd3":0}', '{"cmd2":0}', '{"cmd1":0}']


def test_a_failed_cmd4_is_logged_and_not_marked_as_sent(env):
    service, telemetry, _, station, log, clock = env
    arm_all(env)
    service.start_countdown('A1', True)
    station.fail_writes = True
    clock['now'] += COUNTDOWN_S + 0.1
    feed(telemetry, station, ALL_ACKS)
    notices = service.tick('A1', True)
    assert any(n.level == 'negative' for n in notices)
    assert service.view('A1', True).ignition_sent_at == '' and 'ignicao_falhou' in kinds(log)


def test_changing_the_operation_cancels_the_countdown(env):
    service, *_ = env
    arm_all(env)
    service.start_countdown('A1', True)
    notices = service.operation_changed()
    assert any('mudou' in n.text for n in notices) and not service.view('A1', True).counting