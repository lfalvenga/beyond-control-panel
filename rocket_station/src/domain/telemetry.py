import json
import math
import uuid
from collections import deque
from dataclasses import dataclass, field

from src.domain.report import Series

RESERVED = ('rssi', 'packetN', 'ack1', 'ack2', 'ack3', 'ack4')  # link e armação; o resto são variáveis
X_TIME, X_PACKET = '@time', '@packet'  # eixos X especiais (não colidem com nomes de variáveis)


def to_number(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


@dataclass
class Packet:
    raw: dict
    values: dict  # as variáveis (tudo que não é reservado)
    rssi: float | None
    packet_n: int | None
    acks: dict[int, int]  # ack1..ack4 presentes nesta linha


def decode_line(line: str) -> Packet | None:
    """Interpreta uma linha da estação. None se não for um objeto JSON."""
    try:
        message = json.loads(line)
    except ValueError:
        return None
    if not isinstance(message, dict):
        return None
    number = message.get('packetN')
    acks = {}
    for n in (1, 2, 3, 4):
        value = to_number(message.get(f'ack{n}'))
        if value is not None:
            acks[n] = int(value)
    return Packet(
        raw=message,
        values={k: v for k, v in message.items() if k not in RESERVED},
        rssi=to_number(message.get('rssi')),
        packet_n=number if isinstance(number, int) and not isinstance(number, bool) else None,
        acks=acks,
    )


@dataclass
class Variable:
    name: str
    value: object = None
    numeric: bool = False
    updated_at: float = 0.0
    count: int = 0


class LinkMonitor:
    WINDOW = 30  # pacotes recentes no cálculo da taxa de entrega

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.received = 0
        self.invalid = 0
        self.rssi: float | None = None
        self.last_at: float | None = None
        self._numbers: deque = deque(maxlen=self.WINDOW)

    def on_invalid(self) -> None:
        self.invalid += 1

    def on_packet(self, packet: Packet, now: float) -> None:
        self.received += 1
        self.last_at = now
        self.rssi = packet.rssi
        n = packet.packet_n
        if n is not None:
            if self._numbers and n <= self._numbers[-1]:
                self._numbers.clear()  # o contador voltou ao início (zerou ou a estação reiniciou)
            self._numbers.append(n)

    @property
    def delivery_pct(self) -> float | None:
        if len(self._numbers) < 2:
            return None
        return 100.0 * len(self._numbers) / (self._numbers[-1] - self._numbers[0] + 1)

    def silence_s(self, now: float) -> float | None:
        return None if self.last_at is None else now - self.last_at


class LiveHistory:
    def __init__(self, max_packets: int = 100_000) -> None:
        self._items: deque = deque(maxlen=max_packets)  # (segundos, packetN, {variável: valor})

    def clear(self) -> None:
        self._items.clear()

    def add(self, t: float, packet_n: int | None, numbers: dict[str, float]) -> None:
        self._items.append((t, packet_n, numbers))

    def points(self, y: str, x: str, window_s: float | None, max_points: int = 2000) -> list:
        """Pares [x, y] para um gráfico. x: X_TIME, X_PACKET ou o nome de outra variável."""
        if not self._items:
            return []
        cut = self._items[-1][0] - window_s if window_s else None
        found = []
        for t, n, numbers in reversed(self._items):  # do mais novo para o mais antigo
            if cut is not None and t < cut:
                break
            value_y = numbers.get(y)
            value_x = t if x == X_TIME else n if x == X_PACKET else numbers.get(x)
            if value_y is not None and value_x is not None:
                found.append([value_x, value_y])
        found.reverse()
        step = math.ceil(len(found) / max_points)
        if step > 1:  # muitos pontos: reduz só a exibição, sempre mantendo o último
            reduced = found[::step]
            if reduced[-1] is not found[-1]:
                reduced.append(found[-1])
            return reduced
        return found


@dataclass
class ExpectedVariable:
    name: str  # exatamente como a estação envia
    label: str = ''
    unit: str = ''


@dataclass
class LiveChart:
    id: str
    title: str = 'Novo gráfico'
    x: str = X_TIME
    window_s: float | None = 60.0  # só os últimos N segundos; None = tudo
    series: list[Series] = field(default_factory=list)

    @classmethod
    def new(cls) -> 'LiveChart':
        return cls(id=uuid.uuid4().hex[:8])


@dataclass
class TelemetryConfig:
    expected: list[ExpectedVariable] = field(default_factory=list)
    charts: list[LiveChart] = field(default_factory=list)

    def label(self, name: str) -> str:
        for e in self.expected:
            if e.name == name:
                text = e.label or e.name
                return f'{text} ({e.unit})' if e.unit else text
        return name