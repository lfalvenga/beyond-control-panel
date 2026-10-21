import uuid

from rocket_station.application.ports import OperationRepository
from rocket_station.domain.operation import Operation


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
        self._repository.add(operation, replace=replace)
        return operation

    def update(self, operation: Operation) -> Operation:
        operation.normalize_and_validate()
        if not operation.id:  # operação antiga, de antes do id
            operation.id = str(uuid.uuid4())
        self._repository.update(operation)
        return operation

    def list_all(self) -> list[Operation]:
        return self._repository.list_all()

    def delete(self, code: str) -> None:
        self._repository.delete(code)