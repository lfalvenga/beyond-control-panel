import json
from datetime import datetime, timezone

from src.infrastructure.persistence.recycle_bin import FileRecycleBin


def _folder(root, name, deleted_at):
    folder = root / name
    folder.mkdir()
    (folder / 'cadastro.json').write_text(
        json.dumps({'identificacao': {'codigo': 'X', 'deletado_em': deleted_at}}), encoding='utf-8'
    )


def test_purge_expired(tmp_path):
    now = datetime(2026, 11, 5, tzinfo=timezone.utc)
    _folder(tmp_path, 'A-1', '2026-08-01T10:00:00+00:00')  # 96 dias: vence
    _folder(tmp_path, 'B-1', '2026-10-20T10:00:00+00:00')  # 16 dias: fica
    (tmp_path / 'C-20260101-100000-ab12').mkdir()  # sem cadastro: usa o carimbo do nome, vence
    (tmp_path / 'D-sem-data').mkdir()  # sem data nenhuma: nunca apaga

    removed = FileRecycleBin(tmp_path).purge_expired(now, 60)

    assert sorted(removed) == ['A-1', 'C-20260101-100000-ab12']
    assert (tmp_path / 'B-1').exists() and (tmp_path / 'D-sem-data').exists()