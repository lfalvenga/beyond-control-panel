from dataclasses import dataclass

from src.application.calculation_service import CalculationService
from src.application.operation_service import OperationService
from src.application.package_service import PackageService
from src.application.recording_service import RecordingService
from src.application.report_service import ReportService
from src.application.source_service import SourceService
from src.application.telemetry_config_service import TelemetryConfigService
from src.application.telemetry_service import TelemetryService
from src.config import OPERATIONS_DIR, EXAMPLES_DIR
from src.infrastructure.formulas_catalog import FormulasCatalog
from src.infrastructure.persistence.csv_reader import CsvFileReader
from src.infrastructure.persistence.operation_repository import FileOperationRepository
from src.infrastructure.persistence.package_archive import ZipPackageArchive
from src.infrastructure.persistence.report_repository import FileReportRepository
from src.infrastructure.persistence.source_repository import FileSourceRepository
from src.infrastructure.persistence.telemetry_config_repository import (
    FileTelemetryConfigRepository,
)
from src.infrastructure.telemetry.recorder import FileRecordingStorage
from src.infrastructure.telemetry.serial_station import SerialStation
from src.application.activation_service import ActivationService
from src.infrastructure.persistence.command_log import FileCommandLog


@dataclass
class Services:
    operations: OperationService
    examples: OperationService
    packages: PackageService
    sources: SourceService
    report: ReportService
    calculations: CalculationService
    telemetry: TelemetryService
    recording: RecordingService
    telemetry_config: TelemetryConfigService
    activation: ActivationService


def build_services() -> Services:
    OPERATIONS_DIR.mkdir(parents=True, exist_ok=True)
    EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    repository = FileOperationRepository(OPERATIONS_DIR)
    source_repository = FileSourceRepository(OPERATIONS_DIR)
    sources = SourceService(source_repository, CsvFileReader())
    telemetry = TelemetryService(SerialStation())
    recording = RecordingService(FileRecordingStorage(OPERATIONS_DIR), source_repository)
    telemetry.subscribe(recording.on_packet)  # a gravação escuta os pacotes que chegam
    return Services(
        examples=OperationService(FileOperationRepository(EXAMPLES_DIR)),
        operations=OperationService(repository),
        packages=PackageService(repository, ZipPackageArchive(OPERATIONS_DIR)),
        sources=sources,
        report=ReportService(FileReportRepository(OPERATIONS_DIR), sources),
        calculations=CalculationService(FormulasCatalog(), sources),
        telemetry=telemetry,
        recording=recording,
        telemetry_config=TelemetryConfigService(FileTelemetryConfigRepository(OPERATIONS_DIR)),
        activation=ActivationService(telemetry, recording, FileCommandLog(OPERATIONS_DIR)),
    )