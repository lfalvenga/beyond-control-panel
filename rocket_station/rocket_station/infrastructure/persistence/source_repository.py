import shutil
from pathlib import Path

from rocket_station.domain.data_source import Column, DataSource
from rocket_station.domain.enums import SourceKind
from rocket_station.domain.errors import OperationNotFoundError
from rocket_station.infrastructure.persistence.file_storage import read_json, write_json_atomic
from rocket_station.infrastructure.persistence.operation_repository import (
    FILE_NAME as OPERATION_FILE,
)

SOURCES_DIR = 'dados'  # nomes históricos, mantidos por compatibilidade
REGISTRY_FILE = 'fontes.json'
REGISTRY_VERSION = 1


def _to_json(s: DataSource) -> dict:
    return {
        'id': s.id,
        'arquivo': s.file,
        'origem': s.origin,
        'importado_em': s.imported_at,
        'separador': s.separator,
        'codificacao': s.encoding,
        'linhas': s.rows,
        'colunas': [{'original': c.original, 'exibicao': c.display} for c in s.columns],
        'taxa_hz': s.sample_rate_hz,
        'tipo': s.kind.value,
    }


def _from_json(data: dict) -> DataSource:
    return DataSource(
        id=data['id'],
        file=data['arquivo'],
        origin=data['origem'],
        imported_at=data['importado_em'],
        separator=data['separador'],
        encoding=data['codificacao'],
        rows=data['linhas'],
        columns=[Column(c['original'], c['exibicao']) for c in data['colunas']],
        sample_rate_hz=data.get('taxa_hz'),
        kind=SourceKind(data.get('tipo', 'sd')),
    )


class FileSourceRepository:
    def __init__(self, root: Path) -> None:
        self._root = root

    def _dir(self, code: str) -> Path:
        return self._root / code / SOURCES_DIR

    def list_all(self, code: str) -> list[DataSource]:
        file = self._dir(code) / REGISTRY_FILE
        if not file.is_file():
            return []
        return [_from_json(s) for s in read_json(file)['fontes']]

    def save_all(self, code: str, sources: list[DataSource]) -> None:
        directory = self._dir(code)
        directory.mkdir(parents=True, exist_ok=True)
        content = {'schema_version': REGISTRY_VERSION, 'fontes': [_to_json(s) for s in sources]}
        write_json_atomic(directory / REGISTRY_FILE, content)

    def add(self, code: str, source: DataSource, csv_file: Path) -> None:
        if not (self._root / code / OPERATION_FILE).is_file():
            raise OperationNotFoundError(f'A operação {code} não existe mais.')
        sources = self.list_all(code)
        directory = self._dir(code)
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / source.file
        shutil.copyfile(csv_file, destination)
        try:
            self.save_all(code, sources + [source])
        except Exception:
            destination.unlink(missing_ok=True)  # não deixa um CSV sem registro
            raise

    def csv_path(self, code: str, source: DataSource) -> Path:
        return self._dir(code) / source.file

    def register(self, code: str, source: DataSource) -> None:
        self.save_all(code, self.list_all(code) + [source])