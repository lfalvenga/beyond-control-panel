import pytest

from src.domain.recording import RawRecord, build_table
from src.domain.telemetry import X_PACKET, X_TIME, LinkMonitor, LiveHistory, decode_line


def test_decode_separates_link_from_variables():
    packet = decode_line('{"packetN":7,"rssi":-92,"ack1":1,"temperature":27.5}')
    assert packet.packet_n == 7 and packet.rssi == -92 and packet.acks == {1: 1}
    assert packet.values == {'temperature': 27.5}


def test_decode_without_link_is_valid():
    packet = decode_line('{"temperature":27.5,"pressure":105.2}')
    assert packet.rssi is None and packet.packet_n is None and len(packet.values) == 2


@pytest.mark.parametrize('line', ['ruído {{', '[1, 2]', '42', ''])
def test_decode_rejects_what_is_not_an_object(line):
    assert decode_line(line) is None


def packet(n):
    return decode_line(f'{{"packetN":{n}}}')


def test_delivery_rate_counts_lost_packets():
    link = LinkMonitor()
    for n in (1, 2, 4):  # o 3 se perdeu
        link.on_packet(packet(n), 0.0)
    assert link.delivery_pct == pytest.approx(75.0)


def test_counter_going_back_restarts_the_window():
    link = LinkMonitor()
    for n in (1, 2, 3, 1, 2):
        link.on_packet(packet(n), 0.0)
    assert link.delivery_pct == pytest.approx(100.0)


def test_history_window_and_x_modes():
    history = LiveHistory()
    for i in range(10):
        history.add(float(i), i, {'a': i * 2.0, 'b': 1.0})
    assert history.points('a', X_TIME, 2)[0] == [7.0, 14.0]
    assert history.points('a', X_PACKET, None)[-1] == [9, 18.0]
    assert history.points('a', 'b', None)[0] == [1.0, 0.0]


def test_history_downsampling_keeps_the_last_point():
    history = LiveHistory()
    for i in range(5000):
        history.add(float(i), i, {'a': float(i)})
    points = history.points('a', X_TIME, None, max_points=1000)
    assert len(points) <= 1001 and points[-1] == [4999.0, 4999.0]


def test_build_table_unions_columns_and_estimates_rate():
    records = [
        RawRecord(0.0, {'packetN': 1, 'rssi': -90, 'ack1': 1, 'a': 1.5}),
        RawRecord(0.5, {'packetN': 3, 'a': 2.5, 'b': 'x'}),
        RawRecord(1.0, {'packetN': 4, 'b': 'y'}),
    ]
    names, rows, rate = build_table(records)
    assert names == ['t_s', 'packetN', 'rssi', 'a', 'b']
    assert rows[1] == [0.5, 3, '', 2.5, 'x']
    assert rate == pytest.approx(2.0)