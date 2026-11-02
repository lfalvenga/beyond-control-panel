from src.application.ports import TelemetryConfigRepository
from src.domain.telemetry import TelemetryConfig


class TelemetryConfigService:
    def __init__(self, repository: TelemetryConfigRepository) -> None:
        self._repository = repository

    def get(self, code: str) -> TelemetryConfig:
        return self._repository.get(code)

    def save(self, code: str, config: TelemetryConfig) -> None:
        self._repository.save(code, config)