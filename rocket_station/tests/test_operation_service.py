import json

import pytest

from rocket_station.application.operation_service import OperationService
from rocket_station.domain.enums import OperationKind
from rocket_station.domain.errors import OperationExistsError, ValidationError
from rocket_station.infrastructure.persistence.operation_repository import FileOperationRepository


@pytest.fixture
def service(tmp_path):
    return OperationService(FileOperationRepository(tmp_path))


def make(service, **changes):
    op = service.new()
    op.code, op.created_by = '081026A', 'Ana'
    for key, value in changes.items():
        setattr(op, key, value)
    return op


def test_create_assigns_id_and_can_be_read_back(service):
    created = service.create(make(service))
    assert created.id
    assert service.get('081026A').created_by == 'Ana'


def test_invalid_code_is_rejected(service):
    with pytest.raises(ValidationError):
        service.create(make(service, code='../x'))


def test_creator_is_required(service):
    with pytest.raises(ValidationError):
        service.create(make(service, created_by='  '))


def test_static_test_always_uses_activation(service):
    assert service.create(make(service, uses_activation=False)).uses_activation is True


def test_duplicate_code_needs_replace(service):
    service.create(make(service))
    with pytest.raises(OperationExistsError):
        service.create(make(service))
    service.create(make(service), replace=True)


def test_update_keeps_id_and_other_files(service, tmp_path):
    op = service.create(make(service))
    (tmp_path / '081026A' / 'dados.txt').write_text('x')
    op.project = 'Polaris'
    service.update(op)
    assert service.get('081026A').id == op.id
    assert (tmp_path / '081026A' / 'dados.txt').exists()


def test_reads_legacy_file(service, tmp_path):
    legacy = {'schema_version': 1, 'identificacao': {'codigo': 'X1', 'criado_por': 'Bia'}, 'ficha': []}
    (tmp_path / 'X1').mkdir()
    (tmp_path / 'X1' / 'cadastro.json').write_text(json.dumps(legacy), encoding='utf-8')
    op = service.get('X1')
    assert op.kind is OperationKind.STATIC_TEST and op.id == ''