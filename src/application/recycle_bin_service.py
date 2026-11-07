from datetime import datetime

from src.application.ports import RecycleBin


class RecycleBinService:
    def __init__(self, recycle_bin: RecycleBin, days: int) -> None:
        self._bin = recycle_bin
        self._days = days

    def purge_expired(self) -> list[str]:
        return self._bin.purge_expired(datetime.now().astimezone(), self._days)