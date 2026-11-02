import csv
from pathlib import Path


def write_table_csv(path: Path, names: list[str], rows: list[list]) -> None:
    temp = path.with_name(path.name + '.tmp')
    with open(temp, 'w', encoding='utf-8', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(names)
        writer.writerows(rows)
    temp.replace(path)  # troca o arquivo de uma vez só