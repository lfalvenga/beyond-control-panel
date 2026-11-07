import json

import pytest

from src.application.operation_service import OperationService
from src.application.source_service import SourceService
from src.domain.errors import InvalidCsvError, ValidationError
from src.infrastructure.persistence.csv_reader import CsvFileReader
from src.infrastructure.persistence.operation_repository import FileOperationRepository
from src.infrastructure.persistence.source_repository import FileSourceRepository

CSV = 'alt;v;temp\n0;0;25,1\n1,5;0,8;25,3\n'


@pytest.fixture
def env(tmp_path):
    root = tmp_path / 'ops'
    repository = FileOperationRepository(root)
    operations = OperationService(repository)
    op = operations.new()
    op.code, op.created_by = 'A1', 'Ana'
    operations.create(op)
    return SourceService(FileSourceRepository(root), CsvFileReader(), repository), root, tmp_path


def write_csv(tmp_path, text=CSV, name='LOG.CSV', encoding='utf-8'):
    path = tmp_path / name
    path.write_bytes(text.encode(encoding))
    return path


def test_import_keeps_names_and_copies_file_untouched(env):
    sources, root, tmp = env
    file = write_csv(tmp)
    source = sources.import_csv('A1', file, {})
    assert [c.display for c in source.columns] == ['alt', 'v', 'temp']
    assert source.separator == ';' and source.rows == 2
    assert (root / 'A1' / 'dados' / 'sd-001.csv').read_bytes() == file.read_bytes()


def test_rename_and_rate_are_saved(env):
    sources, _, tmp = env
    source = sources.import_csv('A1', write_csv(tmp), {})
    sources.update('A1', source.id, {'v': 'velocidade'}, 100)
    saved = sources.list_sd('A1')[0]
    assert [c.display for c in saved.columns] == ['alt', 'velocidade', 'temp']
    assert saved.sample_rate_hz == 100


def test_duplicate_or_empty_names_are_rejected(env):
    sources, _, tmp = env
    with pytest.raises(ValidationError):
        sources.import_csv('A1', write_csv(tmp), {'v': 'ALT'})
    with pytest.raises(ValidationError):
        sources.import_csv('A1', write_csv(tmp), {'v': ' '}.copy() | {'temp': ' '})


@pytest.mark.parametrize('rate', [0, -5])
def test_invalid_rate_is_rejected(env, rate):
    sources, _, tmp = env
    with pytest.raises(ValidationError):
        sources.import_csv('A1', write_csv(tmp), {}, rate)


def test_header_must_not_be_numbers(env):
    sources, _, tmp = env
    with pytest.raises(InvalidCsvError):
        sources.import_csv('A1', write_csv(tmp, '1;2;3\n4;5;6\n'), {})


def test_ansi_file_is_read(env):
    sources, _, tmp = env
    source = sources.import_csv('A1', write_csv(tmp, 'pressão;temp\n1;2\n', encoding='latin-1'), {})
    assert source.encoding == 'latin-1' and source.columns[0].original == 'pressão'


def test_ids_increment_and_registry_keeps_legacy_keys(env):
    sources, root, tmp = env
    sources.import_csv('A1', write_csv(tmp), {})
    second = sources.import_csv('A1', write_csv(tmp), {})
    assert second.id == 'sd-002'
    data = json.loads((root / 'A1' / 'dados' / 'fontes.json').read_text(encoding='utf-8'))
    assert set(data['fontes'][0]) == {
        'id', 'arquivo', 'origem', 'importado_em', 'separador',
        'codificacao', 'linhas', 'colunas', 'taxa_hz', 'tipo',
    }