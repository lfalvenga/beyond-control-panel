import pytest

from src.application.operation_service import OperationService
from src.application.package_service import PackageService
from src.domain.package import ImportAction, ImportSituation
from src.infrastructure.persistence.operation_repository import FileOperationRepository
from src.infrastructure.persistence.package_archive import ZipPackageArchive


@pytest.fixture
def env(tmp_path):
    root = tmp_path / 'ops'
    repository = FileOperationRepository(root, tmp_path / 'recycle_bin')
    return OperationService(repository), PackageService(repository, ZipPackageArchive(root)), tmp_path


def make(operations, **changes):
    op = operations.new()
    op.code, op.created_by = 'A1', 'Ana'
    for key, value in changes.items():
        setattr(op, key, value)
    return op


def test_same_operation_is_detected(env):
    operations, packages, tmp = env
    operations.create(make(operations))
    packages.export('A1', tmp / 'a1.beyondtest')
    assert packages.inspect(tmp / 'a1.beyondtest').situation is ImportSituation.SAME_OPERATION


def test_import_after_delete_is_new(env):
    operations, packages, tmp = env
    operations.create(make(operations))
    packages.export('A1', tmp / 'a1.beyondtest')
    operations.delete('A1')
    inspection = packages.inspect(tmp / 'a1.beyondtest')
    assert inspection.situation is ImportSituation.NEW
    packages.import_package(inspection, ImportAction.IMPORT)
    assert operations.get('A1').created_by == 'Ana'


def test_clash_keep_both_keeps_the_package_id(env):
    operations, packages, tmp = env
    original = operations.create(make(operations))
    packages.export('A1', tmp / 'a1.beyondtest')
    operations.create(make(operations), replace=True)  # outro teste com o mesmo código
    inspection = packages.inspect(tmp / 'a1.beyondtest')
    assert inspection.situation is ImportSituation.CODE_CLASH
    assert packages.import_package(inspection, ImportAction.KEEP_BOTH) == 'A1-2'
    assert operations.get('A1-2').id == original.id
    assert operations.get('A1-2').code == 'A1-2'


def test_same_operation_keep_both_gets_new_id(env):
    operations, packages, tmp = env
    original = operations.create(make(operations))
    packages.export('A1', tmp / 'a1.beyondtest')
    inspection = packages.inspect(tmp / 'a1.beyondtest')
    packages.import_package(inspection, ImportAction.KEEP_BOTH)
    assert operations.get('A1-2').id != original.id


def test_replace_restores_the_package_version(env):
    operations, packages, tmp = env
    op = operations.create(make(operations))
    packages.export('A1', tmp / 'a1.beyondtest')
    op.project = 'Mudou'
    operations.update(op)
    packages.import_package(packages.inspect(tmp / 'a1.beyondtest'), ImportAction.REPLACE)
    assert operations.get('A1').project == ''


def test_invalid_file_is_reported(env):
    _, packages, tmp = env
    bad = tmp / 'x.beyondtest'
    bad.write_bytes(b'isto nao e um zip')
    assert packages.inspect(bad).situation is ImportSituation.INVALID