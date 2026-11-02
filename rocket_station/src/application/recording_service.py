import time
from datetime import datetime

from src.application.ports import RecordingStorage, SourceRepository
from src.domain.data_source import DataSource
from src.domain.enums import SourceKind
from src.domain.errors import ValidationError
from src.domain.recording import RawRecord, build_table, display_columns
from src.domain.telemetry import Packet, TelemetryConfig


class RecordingService:
    def __init__(
        self, storage: RecordingStorage, sources: SourceRepository, clock=time.monotonic
    ) -> None:
        self._storage = storage
        self._sources = sources
        self._clock = clock
        self._writer = None
        self._started = 0.0
        self.code = ''
        self.recording_id = ''
        self.count = 0
        self.error = ''

    @property
    def recording(self) -> bool:
        return self._writer is not None

    def elapsed_s(self) -> float:
        return self._clock() - self._started

    def start(self, code: str) -> str:
        """Começa a gravar na operação. Levanta OSError se o arquivo não abrir."""
        self.stop()
        recording_id = self._storage.new_id(code)
        self._writer = self._storage.open_raw(code, recording_id)
        self.code, self.recording_id, self.count, self.error = code, recording_id, 0, ''
        self._started = self._clock()
        return recording_id

    def stop(self) -> None:
        if self._writer is not None:
            self._writer.close()
            self._writer = None

    def on_packet(self, packet: Packet, now: float) -> None:
        if self._writer is None:
            return
        try:
            self._writer.write(RawRecord(round(now - self._started, 3), packet.raw))
            self.count += 1
        except OSError as error:
            self.error = f'Falha ao gravar: {error}'
            self.stop()

    def pending(self, code: str) -> list[str]:
        """Gravações com registro bruto que nunca foram finalizadas (ex.: queda de energia)."""
        ignore = self.recording_id if self.recording and self.code == code else ''
        registered = {s.id for s in self._sources.list_all(code)}
        return self._storage.pending(code, registered, ignore)

    def finalize(self, code: str, recording_id: str, config: TelemetryConfig) -> DataSource:
        if recording_id in {s.id for s in self._sources.list_all(code)}:
            raise ValidationError('Esta gravação já foi finalizada.')
        records = self._storage.read_raw(code, recording_id)
        if not records:
            raise ValidationError('A gravação está vazia: nenhum pacote foi recebido.')
        names, rows, rate = build_table(records)
        file = self._storage.write_table(code, recording_id, names, rows)
        source = DataSource(
            id=recording_id,
            file=file,
            origin='Telemetria (rádio)',
            imported_at=datetime.now().isoformat(timespec='seconds'),
            separator=',',
            encoding='utf-8',
            rows=len(records),
            columns=display_columns(names, config),
            sample_rate_hz=rate,
            kind=SourceKind.RADIO,
        )
        self._sources.register(code, source)
        return source

    def finish_active(self, config: TelemetryConfig) -> DataSource:
        code, recording_id = self.code, self.recording_id
        self.stop()
        return self.finalize(code, recording_id, config)