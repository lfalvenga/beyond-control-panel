from datetime import datetime
from pathlib import Path

from rocket_station.application.ports import CsvReader, SourceRepository
from rocket_station.domain.data_source import (
    Column,
    CsvPreview,
    DataSource,
    validate_columns,
    validate_sample_rate,
)
from rocket_station.domain.enums import SourceKind
from rocket_station.domain.errors import ValidationError


class SourceService:
    def __init__(self, repository: SourceRepository, csv_reader: CsvReader) -> None:
        self._repository = repository
        self._csv = csv_reader

    def list_sd(self, code: str) -> list[DataSource]:
        return [s for s in self._repository.list_all(code) if s.kind is SourceKind.SD]

    def preview(self, file: Path) -> CsvPreview:
        return self._csv.preview(file)

    def import_csv(
        self, code: str, file: Path, names: dict[str, str], sample_rate_hz: float | None = None
    ) -> DataSource:
        rate = validate_sample_rate(sample_rate_hz)
        preview = self._csv.preview(file, max_rows=0)
        columns = [Column(o, (names.get(o) or o).strip()) for o in preview.columns]
        validate_columns(columns)
        existing = self._repository.list_all(code)
        number = max(
            (int(s.id.split('-')[1]) for s in existing if s.id.startswith('sd-')), default=0
        ) + 1
        source = DataSource(
            id=f'sd-{number:03d}',
            file=f'sd-{number:03d}.csv',
            origin=file.name,
            imported_at=datetime.now().isoformat(timespec='seconds'),
            separator=preview.separator,
            encoding=preview.encoding,
            rows=preview.total_rows,
            columns=columns,
            sample_rate_hz=rate,
        )
        self._repository.add(code, source, file)  # cópia fiel do CSV, sem alterar
        return source

    def update(
        self, code: str, source_id: str, names: dict[str, str], sample_rate_hz: float | None
    ) -> None:
        rate = validate_sample_rate(sample_rate_hz)
        sources = self._repository.list_all(code)
        for source in sources:
            if source.id == source_id:
                for column in source.columns:
                    column.display = (names.get(column.original) or column.original).strip()
                validate_columns(source.columns)
                source.sample_rate_hz = rate
                self._repository.save_all(code, sources)
                return
        raise ValidationError('Fonte não encontrada.')

    def rows(self, code: str, source: DataSource, limit: int = 5000) -> list[list[str]]:
        path = self._repository.csv_path(code, source)
        return self._csv.rows(path, source.separator, source.encoding, limit)

    def list_all(self, code: str) -> list[DataSource]:
        return self._repository.list_all(code)

    def numeric_columns(self, code: str, source: DataSource) -> dict[str, list[float | None]]:
        path = self._repository.csv_path(code, source)
        return self._csv.numeric_columns(path, source.separator, source.encoding)

    def numeric_variables(self, code: str, source: DataSource) -> dict[str, str]:
        """Colunas numéricas: nome original -> nome de exibição."""
        names = {c.original: c.display for c in source.columns}
        return {column: names.get(column, column) for column in self.numeric_columns(code, source)}