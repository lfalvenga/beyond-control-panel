import shutil
from pathlib import Path
import uuid
from datetime import datetime

from src.config import FORMAT_VERSION
from src.domain.enums import OperationKind, Review
from src.domain.errors import OperationExistsError, OperationNotFoundError
from src.domain.operation import Operation, Parameter
from src.infrastructure.persistence.file_storage import read_json, write_json_atomic
from src.domain.operation import Measure, Operation, Parameter

from src.domain.clock import now_iso

FILE_NAME = 'cadastro.json'  # nome histórico, mantido por compatibilidade

_KIND_TO_JSON = {OperationKind.STATIC_TEST: 'teste_estatico', OperationKind.FLIGHT: 'voo'}
_REVIEW_TO_JSON = {
    Review.PENDING: 'Pendente',
    Review.APPROVED: 'Deferido',
    Review.REJECTED: 'Indeferido',
    Review.NOT_APPLICABLE: 'Não se aplica',
}
_KIND_FROM_JSON = {v: k for k, v in _KIND_TO_JSON.items()}
_REVIEW_FROM_JSON = {v: k for k, v in _REVIEW_TO_JSON.items()}


def _to_json(op: Operation) -> dict:
    return {
        'schema_version': FORMAT_VERSION,
        'id': op.id,
        'identificacao': {
            'codigo': op.code,
            'tipo': _KIND_TO_JSON[op.kind],
            'usa_acionamento': op.uses_activation,
            'projeto': op.project,
            'data': op.date,
            'local': op.location,
            'equipe': op.team,
            'criado_por': op.created_by,
            'classificacao': op.classification,
            'observacoes': op.notes,
            'criado_em': op.created_at,
            'atualizado_em':op.updated_at,
            'deletado_em':op.deleted_at,
        },
        'ficha': [
            {
                'nome': p.name,
                'medidas': [
                    {'nome': m.name, 'unidade': m.unit, 'valor': m.value} for m in p.measures
                ],
                'responsavel': p.responsible,
                'horario': p.time,
                'parecer': _REVIEW_TO_JSON[p.review],
            }
            for p in op.parameters
        ],
    }

def _measures_from_json(p: dict) -> list[Measure]:
    if 'medidas' in p:
        return [Measure(m['nome'], m.get('unidade', ''), m.get('valor')) for m in p['medidas']]
    return [Measure(p['nome'], p.get('unidade', ''), p.get('valor'))] 

def operation_from_json(data: dict) -> Operation:
    ident = data['identificacao']
    return Operation(
        id=data.get('id', ''),
        code=ident['codigo'],
        kind=_KIND_FROM_JSON[ident.get('tipo', 'teste_estatico')],
        uses_activation=ident.get('usa_acionamento', True),
        project=ident.get('projeto', ''),
        date=ident.get('data', ''),
        location=ident.get('local', ''),
        team=ident.get('equipe', ''),
        created_by=ident.get('criado_por', ''),
        created_at=ident.get('criado_em', ''),
        updated_at=ident.get('atualizado_em', ''),
        deleted_at=ident.get('deletado_em', ''),
        classification=ident.get('classificacao', ''),
        notes=ident.get('observacoes', ''),
        parameters=[
            Parameter(
                name=p['nome'],
                measures=_measures_from_json(p),
                responsible=p.get('responsavel', ''),
                time=p.get('horario', ''),
                review=_REVIEW_FROM_JSON[p.get('parecer', 'Pendente')],
            )
            for p in data['ficha']
        ],
    )


class FileOperationRepository:
    def __init__(self, root: Path, recycle_bin: Path | None = None) -> None:
        self._root = root
        self._recycle_bin = recycle_bin

    def _file(self, code: str) -> Path:
        return self._root / code / FILE_NAME

    def exists(self, code: str) -> bool:
        return self._file(code).is_file()

    def get(self, code: str) -> Operation:
        if not self.exists(code):
            raise OperationNotFoundError(f'O teste {code} não existe mais.')
        return operation_from_json(read_json(self._file(code)))

    def add(self, operation: Operation, *, replace: bool = False) -> None:
        folder = self._root / operation.code
        if folder.exists():
            if not replace:
                raise OperationExistsError(operation.code)
            shutil.rmtree(folder)
        folder.mkdir(parents=True)
        write_json_atomic(self._file(operation.code), _to_json(operation))

    def update(self, operation: Operation) -> None:
        if not self.exists(operation.code):
            raise OperationNotFoundError(f'O teste {operation.code} não existe mais.')
        write_json_atomic(self._file(operation.code), _to_json(operation))  # só o cadastro

    def list_all(self) -> list[Operation]:
        if not self._root.is_dir():
            return []
        operations = []
        for folder in sorted(self._root.iterdir()):
            if not (folder / FILE_NAME).is_file():
                continue
            try:
                operations.append(operation_from_json(read_json(folder / FILE_NAME)))
            except (OSError, ValueError, KeyError, TypeError):
                continue  # cadastro ilegível: não derruba a lista
        return operations

    def delete(self, code: str) -> None:
        """Move para a lixeira. Nada é apagado de vez."""
        if not self.exists(code):
            raise OperationNotFoundError(f'O teste {code} não existe mais.')
        if self._recycle_bin is None:
            raise OSError('Este repositório não tem lixeira.')
        trash = self._recycle_bin
        trash.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        shutil.move(str(self._root / code), str(trash / f'{code}-{stamp}-{uuid.uuid4().hex[:4]}'))

    def free_code(self, code: str) -> str:
        n = 2
        while (self._root / f'{code}-{n}').exists():
            n += 1
        return f'{code}-{n}'

    def touch(self, code: str) -> None:
        file = self._root / code / FILE_NAME
        if not file.is_file():
            return
        data = read_json(file)
        data['identificacao']['atualizado_em'] = now_iso()
        write_json_atomic(file, data)