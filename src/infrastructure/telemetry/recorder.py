import json
from pathlib import Path

from src.domain.recording import RawRecord
from src.infrastructure.persistence.source_repository import SOURCES_DIR
from src.infrastructure.telemetry.csv_converter import write_table_csv


class _RawWriter:
    def __init__(self, path: Path) -> None:
        self._file = open(path, 'a', encoding='utf-8')

    def write(self, record: RawRecord) -> None:
        line = json.dumps({'t_s': record.t_s, 'msg': record.message}, ensure_ascii=False)
        self._file.write(line + '\n')
        self._file.flush()  # se o app travar, nada se perde

    def close(self) -> None:
        self._file.close()


class FileRecordingStorage:
    def __init__(self, root: Path) -> None:
        self._root = root

    def _dir(self, code: str) -> Path:
        return self._root / code / SOURCES_DIR

    def new_id(self, code: str) -> str:
        folder = self._dir(code)
        numbers = []
        if folder.is_dir():
            for file in folder.glob('radio-*'):
                part = file.stem.split('-')[1]
                if part.isdigit():
                    numbers.append(int(part))
        return f'radio-{max(numbers, default=0) + 1:03d}'

    def open_raw(self, code: str, recording_id: str) -> _RawWriter:
        folder = self._dir(code)
        folder.mkdir(parents=True, exist_ok=True)
        return _RawWriter(folder / f'{recording_id}.jsonl')

    def read_raw(self, code: str, recording_id: str) -> list[RawRecord]:
        records = []
        with open(self._dir(code) / f'{recording_id}.jsonl', encoding='utf-8') as file:
            for line in file:
                try:
                    data = json.loads(line)
                    records.append(RawRecord(data['t_s'], data['msg']))
                except (ValueError, KeyError, TypeError):
                    continue  # linha cortada por uma queda de energia
        return records

    def write_table(self, code: str, recording_id: str, names: list[str], rows: list[list]) -> str:
        name = f'{recording_id}.csv'
        write_table_csv(self._dir(code) / name, names, rows)
        return name

    def pending(self, code: str, registered: set[str], ignore: str = '') -> list[str]:
        folder = self._dir(code)
        if not folder.is_dir():
            return []
        result = []
        for file in sorted(folder.glob('radio-*.jsonl')):
            if file.stem in registered or file.stem == ignore:
                continue
            if file.stat().st_size == 0:
                file.unlink()  # gravação que nunca recebeu nada
                continue
            result.append(file.stem)
        return result