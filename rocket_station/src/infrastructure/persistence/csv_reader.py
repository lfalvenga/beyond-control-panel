import csv
import io
import math
from functools import lru_cache
from pathlib import Path

from src.domain.data_source import CsvPreview
from src.domain.errors import InvalidCsvError

MAX_SIZE = 50 * 1024 * 1024  # 50 MB
SEPARATORS = (',', ';', '\t')


def _decode(file: Path) -> tuple[str, str]:
    if file.stat().st_size > MAX_SIZE:
        raise InvalidCsvError('Arquivo grande demais (o limite é 50 MB).')
    raw = file.read_bytes()
    try:
        return raw.decode('utf-8-sig'), 'utf-8-sig'
    except UnicodeDecodeError:
        return raw.decode('latin-1'), 'latin-1'


def _detect_separator(text: str) -> str:
    first = next((line for line in text.splitlines() if line.strip()), '')
    return max(SEPARATORS, key=first.count)  # empate ou nenhum: vírgula


def _looks_like_number(text: str) -> bool:
    try:
        float(text.replace(',', '.'))
        return True
    except ValueError:
        return False


def _unique_names(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    result = []
    for i, name in enumerate(names):
        base = name or f'coluna_{i + 1}'
        seen[base] = seen.get(base, 0) + 1
        result.append(base if seen[base] == 1 else f'{base}_{seen[base]}')
    return result


def _fit(row: list[str], n: int) -> list[str]:
    return (row + [''] * n)[:n]


def _split(text: str, separator: str) -> tuple[list[str], list[list[str]]]:
    reader = csv.reader(io.StringIO(text, newline=''), delimiter=separator)
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        raise InvalidCsvError('O arquivo está vazio.')
    first = [cell.strip() for cell in rows[0]]
    if all(_looks_like_number(cell) for cell in first if cell):
        raise InvalidCsvError(
            'O arquivo precisa ter uma linha de cabeçalho com os nomes das variáveis.'
        )
    return _unique_names(first), rows[1:]


def _convert_column(cells: list[str]) -> list[float | None] | None:
    """Converte uma coluna para números. Devolve None se ela não for numérica."""
    values: list[float | None] = []
    any_value = False
    for cell in cells:
        cell = cell.strip()
        if not cell:
            values.append(None)  # célula vazia vira lacuna, não zero
            continue
        try:
            number = float(cell.replace(',', '.'))  # aceita vírgula decimal
        except ValueError:
            return None
        values.append(number if math.isfinite(number) else None)
        any_value = True
    return values if any_value else None


@lru_cache(maxsize=4)
def _numeric(
    path: str, modified_ns: int, encoding: str, separator: str
) -> dict[str, list[float | None]]:
    text = Path(path).read_bytes().decode(encoding)
    names, rows = _split(text, separator)
    fitted = [_fit(row, len(names)) for row in rows]
    result = {}
    for name, cells in zip(names, zip(*fitted)):
        values = _convert_column(list(cells))
        if values is not None:
            result[name] = values
    return result

class CsvFileReader:
    def preview(self, file: Path, max_rows: int = 10) -> CsvPreview:
        text, encoding = _decode(file)
        separator = _detect_separator(text)
        columns, rows = _split(text, separator)
        return CsvPreview(
            columns=columns,
            rows=[_fit(row, len(columns)) for row in rows[:max_rows]],
            total_rows=len(rows),
            separator=separator,
            encoding=encoding,
        )

    def rows(self, file: Path, separator: str, encoding: str, limit: int) -> list[list[str]]:
        text = file.read_bytes().decode(encoding)
        columns, rows = _split(text, separator)
        return [_fit(row, len(columns)) for row in rows[:limit]]

    def numeric_columns(self, file: Path, separator: str, encoding: str) -> dict[str, list[float | None]]:
        return _numeric(str(file), file.stat().st_mtime_ns, encoding, separator)