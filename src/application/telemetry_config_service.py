from src.application.ports import TelemetryConfigRepository
from src.domain.telemetry import TelemetryConfig
from src.application.ports import OperationRepository


class TelemetryConfigService:
    def __init__(self, repository: TelemetryConfigRepository, operations: OperationRepository) -> None:
        self._operations = operations
        self._repository = repository

    def get(self, code: str) -> TelemetryConfig:
        return self._repository.get(code)

    def save(self, code: str, config: TelemetryConfig) -> None:
        self._operations.touch(code)
        self._repository.save(code, config)