import json
import time
from collections import deque
from datetime import datetime

from src.application.ports import StationPort
from src.domain.telemetry import (
    LinkMonitor,
    LiveHistory,
    Variable,
    decode_line,
    to_number,
)


class TelemetryService:
    def __init__(self, station: StationPort, clock=time.monotonic) -> None:
        self._station = station
        self._clock = clock
        self._listeners: list = []
        self._raw: deque = deque(maxlen=200)
        self._raw_count = 0
        self._started = clock()
        self.link = LinkMonitor()
        self.history = LiveHistory()
        self.variables: dict[str, Variable] = {}
        self.acks: dict[int, int] = {}  # último ackN recebido (ausente = sem informação)
        self.acks_at: dict[int, str] = {}  # horário em que cada ackN passou a 1
        self.ack_changes: list = []  # (n, valor anterior, valor novo), consumidas pelo painel
        self.error = ''
        self.source = ''

    @property
    def connected(self) -> bool:
        return self._station.is_open

    @property
    def seconds_since_last_packet(self) -> float | None:
        return self.link.silence_s(self._clock())

    def subscribe(self, callback) -> None:
        """callback(packet, now) é chamado a cada pacote válido."""
        self._listeners.append(callback)

    def ports(self) -> list[tuple[str, str]]:
        return self._station.list_ports()

    def connect(self, port: str, baud: int = 115200) -> None:
        self.disconnect()
        self.link.reset()
        self.history.clear()
        for collection in (self.variables, self.acks, self.acks_at, self._raw):
            collection.clear()
        self.ack_changes.clear()
        self._raw_count = 0
        self.error = ''
        self.source = port
        self._started = self._clock()
        self._station.open(port, baud)

    def disconnect(self) -> None:
        self._station.close()

    def send(self, message: dict) -> None:
        """Envia uma linha JSON para a estação. Levanta ConnectionError se não conseguir."""
        if not self.connected:
            raise ConnectionError('A estação não está conectada.')
        self._station.write_line(json.dumps(message, separators=(',', ':')))

    def poll(self) -> None:
        error = self._station.take_error()
        if error:
            self.error = f'Conexão perdida: {error}'
        for line in self._station.read_lines():
            self._raw.append(line)
            self._raw_count += 1
            self._handle(line)

    def raw_since(self, seen: int) -> tuple[list[str], int]:
        """Linhas brutas chegadas depois da contagem `seen` (para o monitor)."""
        new = min(self._raw_count - seen, len(self._raw))
        return (list(self._raw)[-new:] if new > 0 else []), self._raw_count

    def _handle(self, line: str) -> None:
        packet = decode_line(line)
        if packet is None:
            self.link.on_invalid()
            return
        now = self._clock()
        self.link.on_packet(packet, now)
        numbers = {}
        for name, value in packet.values.items():
            variable = self.variables.setdefault(name, Variable(name))
            number = to_number(value)
            variable.numeric = number is not None
            variable.value = number if number is not None else value
            variable.updated_at = now
            variable.count += 1
            if number is not None:
                numbers[name] = number
        self.history.add(now - self._started, packet.packet_n, numbers)
        for n, value in packet.acks.items():
            self._register_ack(n, value)
        for callback in self._listeners:
            callback(packet, now)

    def _register_ack(self, n: int, value: int) -> None:
        previous = self.acks.get(n)
        self.acks[n] = value
        if previous != value and not (previous is None and value == 0):
            if value == 1:
                self.acks_at[n] = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            self.ack_changes.append((n, previous, value))