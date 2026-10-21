from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from rocket_station.domain.operation import Operation


class ImportSituation(str, Enum):
    NEW = 'new'
    SAME_OPERATION = 'same_operation'  # mesmo código e mesmo id
    CODE_CLASH = 'code_clash'  # mesmo código, mas outra operação
    INVALID = 'invalid'


class ImportAction(str, Enum):
    IMPORT = 'import'
    REPLACE = 'replace'
    KEEP_BOTH = 'keep_both'
    SKIP = 'skip'


@dataclass
class PackageInspection:
    file: Path
    situation: ImportSituation
    code: str = ''
    operation: Operation | None = None
    existing: Operation | None = None
    error: str = ''