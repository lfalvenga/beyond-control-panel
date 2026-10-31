from dataclasses import dataclass

from rocket_station.application.calculation_service import CalculationService
from rocket_station.application.operation_service import OperationService
from rocket_station.application.package_service import PackageService
from rocket_station.application.recording_service import RecordingService
from rocket_station.application.report_service import ReportService
from rocket_station.application.source_service import SourceService
from rocket_station.application.telemetry_config_service import TelemetryConfigService
from rocket_station.application.telemetry_service import TelemetryService
from rocket_station.config import OPERATIONS_DIR
from rocket_station.infrastructure.formulas_catalog import FormulasCatalog
from rocket_station.infrastructure.persistence.csv_reader import CsvFileReader
from rocket_station.infrastructure.persistence.operation_repository import FileOperationRepository
from rocket_station.infrastructure.persistence.package_archive import ZipPackageArchive
from rocket_station.infrastructure.persistence.report_repository import FileReportRepository
from rocket_station.infrastructure.persistence.source_repository import FileSourceRepository
from rocket_station.infrastructure.persistence.telemetry_config_repository import (
    FileTelemetryConfigRepository,
)
from rocket_station.infrastructure.telemetry.recorder import FileRecordingStorage
from rocket_station.infrastructure.telemetry.serial_station import SerialStation
from rocket_station.application.activation_service import ActivationService
from rocket_station.infrastructure.persistence.command_log import FileCommandLog


@dataclass
class Services:
    operations: OperationService
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
    repository = FileOperationRepository(OPERATIONS_DIR)
    source_repository = FileSourceRepository(OPERATIONS_DIR)
    sources = SourceService(source_repository, CsvFileReader())
    telemetry = TelemetryService(SerialStation())
    recording = RecordingService(FileRecordingStorage(OPERATIONS_DIR), source_repository)
    telemetry.subscribe(recording.on_packet)  # a gravação escuta os pacotes que chegam
    return Services(
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