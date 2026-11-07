import re
import shutil
from datetime import datetime
from pathlib import Path

from src.domain.recycle_bin import is_expired
from src.infrastructure.persistence.file_storage import read_json
from src.infrastructure.persistence.operation_repository import FILE_NAME as OPERATION_FILE


class FileRecycleBin:
    def __init__(self, root: Path) -> None:
        self._root = root

    def purge_expired(self, now: datetime, days: int) -> list[str]:
        removed: list[str] = []
        if not self._root.is_dir():
            return removed
        for folder in self._root.iterdir():
            if not folder.is_dir():
                continue
            deleted_at = self._deleted_at(folder)
            if deleted_at is None or not is_expired(deleted_at, now, days):
                continue  # sem data confiável: não apaga
            try:
                shutil.rmtree(folder)
            except OSError:
                continue  # em uso (Windows, por exemplo): tenta de novo na próxima abertura
            removed.append(folder.name)
        return removed

    def _deleted_at(self, folder: Path) -> datetime | None:
        try:
            value = read_json(folder / OPERATION_FILE)['identificacao'].get('deletado_em')
            if value:
                moment = datetime.fromisoformat(value)
                return moment if moment.tzinfo else moment.astimezone()
        except (OSError, ValueError, KeyError, TypeError):
            pass
        # exclusões antigas, sem o campo: usa o carimbo do nome da pasta
        match = re.search(r'-(\d{8}-\d{6})-[0-9a-f]{4}$', folder.name)
        if match:
            try:
                return datetime.strptime(match.group(1), '%Y%m%d-%H%M%S').astimezone()
            except ValueError:
                pass
        return None