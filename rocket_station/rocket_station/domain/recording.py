from dataclasses import dataclass

from rocket_station.domain.data_source import Column
from rocket_station.domain.telemetry import RESERVED, TelemetryConfig

LINK_COLUMNS = ('packetN', 'rssi')
LINK_LABELS = {'t_s': 'Tempo (s)', 'packetN': 'Nº do pacote', 'rssi': 'RSSI (dBm)'}


@dataclass
class RawRecord:
    t_s: float  # segundos desde o início da gravação
    message: dict  # a linha como chegou da estação


def _cell(value):
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float, str)):
        return value
    return '' if value is None else str(value)


def build_table(records: list[RawRecord]) -> tuple[list[str], list[list], float | None]:
    """Colunas (tempo, link, variáveis), linhas e a taxa média em Hz (pacotes ÷ duração)."""
    variables: list[str] = []
    for record in records:
        for name in record.message:
            if name not in RESERVED and name not in variables:
                variables.append(name)
    link = [c for c in LINK_COLUMNS if any(c in r.message for r in records)]
    names = ['t_s', *link, *variables]
    rows = [[r.t_s] + [_cell(r.message.get(n, '')) for n in names[1:]] for r in records]
    duration = records[-1].t_s - records[0].t_s if records else 0
    rate = (len(records) - 1) / duration if len(records) > 1 and duration > 0 else None
    return names, rows, rate


def display_columns(names: list[str], config: TelemetryConfig) -> list[Column]:
    base = dict(LINK_LABELS)
    for e in config.expected:
        if e.name:
            base[e.name] = config.label(e.name)
    used: set[str] = set()
    columns = []
    for name in names:
        shown = base.get(name, name)
        if shown.lower() in used:
            shown = name
        if shown.lower() in used:
            shown = f'{name} ({len(used)})'
        used.add(shown.lower())
        columns.append(Column(name, shown))
    return columns