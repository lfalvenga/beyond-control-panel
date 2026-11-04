import uuid

from src.application.ports import OperationRepository
from src.domain.operation import Operation
from datetime import datetime
from src.domain.clock import now_iso


class OperationService:
    def __init__(self, repository: OperationRepository) -> None:
        self._repository = repository

    def new(self) -> Operation:
        return Operation.blank()

    def get(self, code: str) -> Operation:
        return self._repository.get(code)

    def create(self, operation: Operation, *, replace: bool = False) -> Operation:
        operation.normalize_and_validate()
        operation.id = str(uuid.uuid4())  # criar é sempre uma operação nova: id novo
        operation.created_at = now_iso()
        operation.updated_at = operation.created_at
        self._repository.add(operation, replace=replace)
        return operation

    def update(self, operation: Operation) -> Operation:
        operation.normalize_and_validate()
        if not operation.id:  # operação antiga, de antes do id
            operation.id = str(uuid.uuid4())
        self._repository.update(operation)
        operation.updated_at = now_iso();
        return operation

    def list_all(self) -> list[Operation]:
        return self._repository.list_all()

    def delete(self, code: str) -> None:
        operation = self._repository.get(code)
        operation.deleted_at = now_iso()
        operation.updated_at = operation.deleted_at
        self._repository.update(operation) 
        self._repository.delete(code)