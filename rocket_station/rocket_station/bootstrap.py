from dataclasses import dataclass

from rocket_station.application.calculation_service import CalculationService
from rocket_station.application.operation_service import OperationService
from rocket_station.application.package_service import PackageService
from rocket_station.application.report_service import ReportService
from rocket_station.application.source_service import SourceService
from rocket_station.config import OPERATIONS_DIR
from rocket_station.infrastructure.formulas_catalog import FormulasCatalog
from rocket_station.infrastructure.persistence.csv_reader import CsvFileReader
from rocket_station.infrastructure.persistence.operation_repository import FileOperationRepository
from rocket_station.infrastructure.persistence.package_archive import ZipPackageArchive
from rocket_station.infrastructure.persistence.report_repository import FileReportRepository
from rocket_station.infrastructure.persistence.source_repository import FileSourceRepository


@dataclass
class Services:
    operations: OperationService
    packages: PackageService
    sources: SourceService
    report: ReportService
    calculations: CalculationService


def build_services() -> Services:
    OPERATIONS_DIR.mkdir(parents=True, exist_ok=True)
    repository = FileOperationRepository(OPERATIONS_DIR)
    sources = SourceService(FileSourceRepository(OPERATIONS_DIR), CsvFileReader())
    return Services(
        operations=OperationService(repository),
        packages=PackageService(repository, ZipPackageArchive(OPERATIONS_DIR)),
        sources=sources,
        report=ReportService(FileReportRepository(OPERATIONS_DIR), sources),
        calculations=CalculationService(FormulasCatalog(), sources),
    )