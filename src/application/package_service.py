import uuid
from pathlib import Path

from src.application.ports import OperationRepository, PackageArchive
from src.domain.errors import InvalidPackageError, OperationNotFoundError
from src.domain.package import ImportAction, ImportSituation, PackageInspection


class PackageService:
    def __init__(self, repository: OperationRepository, archive: PackageArchive) -> None:
        self._repository = repository
        self._archive = archive

    def export(self, code: str, destination: Path) -> Path:
        self._archive.export(code, destination)
        return destination

    def inspect(self, file: Path) -> PackageInspection:
        """Classifica o pacote sem gravar nada."""
        try:
            operation = self._archive.read(file)
        except InvalidPackageError as error:
            return PackageInspection(file, ImportSituation.INVALID, error=str(error))
        code = operation.code
        if not self._repository.exists(code):
            return PackageInspection(file, ImportSituation.NEW, code, operation)
        try:
            existing = self._repository.get(code)
        except (OperationNotFoundError, OSError, ValueError, KeyError, TypeError):
            existing = None
        same = existing is not None and existing.id != '' and existing.id == operation.id
        situation = ImportSituation.SAME_OPERATION if same else ImportSituation.CODE_CLASH
        return PackageInspection(file, situation, code, operation, existing)

    def import_package(self, inspection: PackageInspection, action: ImportAction) -> str:
        """Instala o pacote e devolve o código com que a operação ficou salva."""
        if action == ImportAction.SKIP or inspection.operation is None:
            raise ValueError('Não há nada para importar.')
        source = inspection.code
        if action == ImportAction.KEEP_BOTH:
            target = self._repository.free_code(source)
            self._archive.install(inspection.file, source, target, replace=False)
            operation = self._repository.get(target)
            operation.code = target
            # a cópia de uma MESMA operação precisa de id novo; um teste diferente mantém o seu
            if inspection.situation == ImportSituation.SAME_OPERATION or not operation.id:
                operation.id = str(uuid.uuid4())
            self._repository.update(operation)
            return target
        self._archive.install(
            inspection.file, source, source, replace=action == ImportAction.REPLACE
        )
        return source