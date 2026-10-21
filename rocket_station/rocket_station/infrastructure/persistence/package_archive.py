import json
import shutil
import zipfile
from pathlib import Path, PurePosixPath
from uuid import uuid4

from rocket_station.config import FORMAT_VERSION
from rocket_station.domain.errors import InvalidPackageError
from rocket_station.domain.operation import CODE_PATTERN, Operation
from rocket_station.infrastructure.persistence.operation_repository import (
    FILE_NAME,
    operation_from_json,
)


class ZipPackageArchive:
    def __init__(self, root: Path) -> None:
        self._root = root

    def export(self, code: str, destination: Path) -> None:
        folder = self._root / code
        if not (folder / FILE_NAME).is_file():
            raise FileNotFoundError(f'Teste {code} não encontrado.')
        try:
            with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as package:
                for file in sorted(folder.rglob('*')):
                    if not file.is_file() or file.resolve() == destination.resolve():
                        continue
                    package.write(file, arcname=f'{code}/{file.relative_to(folder).as_posix()}')
        except Exception:
            destination.unlink(missing_ok=True)  # não deixa um pacote incompleto
            raise

    def read(self, file: Path) -> Operation:
        try:
            with zipfile.ZipFile(file) as package:
                tops = set()
                for name in package.namelist():
                    parts = PurePosixPath(name).parts
                    if '\\' in name or name.startswith('/') or '..' in parts or not parts:
                        raise InvalidPackageError('O pacote contém caminhos inválidos.')
                    tops.add(parts[0])
                if len(tops) != 1:
                    raise InvalidPackageError('O pacote deve ter uma única pasta de teste.')
                code = tops.pop()
                if not CODE_PATTERN.fullmatch(code):
                    raise InvalidPackageError('O código do pacote é inválido.')
                try:
                    data = json.loads(package.read(f'{code}/{FILE_NAME}'))
                except KeyError:
                    raise InvalidPackageError('O pacote não tem cadastro.json.') from None
                if data.get('schema_version', 0) > FORMAT_VERSION:
                    raise InvalidPackageError(
                        'Pacote gerado por uma versão mais nova do aplicativo.'
                    )
                operation = operation_from_json(data)
        except InvalidPackageError:
            raise
        except (zipfile.BadZipFile, OSError):
            raise InvalidPackageError('Arquivo inválido ou corrompido.') from None
        except (ValueError, KeyError, TypeError):
            raise InvalidPackageError('O cadastro do pacote está ilegível.') from None
        if operation.code != code:
            raise InvalidPackageError('O código do cadastro não bate com a pasta do pacote.')
        return operation

    def install(self, file: Path, source_code: str, target_code: str, *, replace: bool) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        temp = self._root / f'.importing-{uuid4().hex}'
        try:
            with zipfile.ZipFile(file) as package:
                package.extractall(temp)
            extracted = temp / source_code
            destination = self._root / target_code
            old = None
            if destination.exists():
                if not replace:
                    raise FileExistsError(f'Já existe um teste {target_code}.')
                old = temp / 'old'
                destination.rename(old)  # guarda o antigo até o novo estar no lugar
            try:
                extracted.rename(destination)
            except OSError:
                if old is not None:
                    old.rename(destination)  # deu errado: devolve o antigo
                raise
        finally:
            shutil.rmtree(temp, ignore_errors=True)