import json
from datetime import datetime
from pathlib import Path

FILE_NAME = 'comandos.jsonl'  # nome histórico, mantido por compatibilidade


class FileCommandLog:
    def __init__(self, root: Path) -> None:
        self._root = root

    def append(self, code: str, event: dict) -> None:
        folder = self._root / code
        if not folder.is_dir():
            return
        record = {'t': datetime.now().isoformat(timespec='milliseconds'), **event}
        with open(folder / FILE_NAME, 'a', encoding='utf-8') as file:
            file.write(json.dumps(record, ensure_ascii=False) + '\n')

    def read(self, code: str) -> list[dict]:
        file = self._root / code / FILE_NAME
        if not file.is_file():
            return []
        events = []
        with open(file, encoding='utf-8') as lines:
            for line in lines:
                try:
                    events.append(json.loads(line))
                except ValueError:
                    continue  # linha cortada por uma queda de energia
        return events