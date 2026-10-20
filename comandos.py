"""Histórico de comandos e confirmações de uma operação (comandos.jsonl, só acrescenta)."""

import json
import time
from datetime import datetime

from armazenamento import PASTA_TESTES
from estacao_solo import estacao


def registrar(codigo: str, evento: str, **dados) -> dict:
    registro = {'t': datetime.now().isoformat(timespec='milliseconds'), 'evento': evento, **dados}
    if estacao.gravando and estacao.gravacao_codigo == codigo:  # liga o evento ao tempo da gravação
        registro['gravacao'] = estacao.gravacao_ident
        registro['t_s'] = round(time.monotonic() - estacao.gravacao_inicio, 3)
    pasta = PASTA_TESTES / codigo
    if pasta.is_dir():
        with open(pasta / 'comandos.jsonl', 'a', encoding='utf-8') as arquivo:
            arquivo.write(json.dumps(registro, ensure_ascii=False) + '\n')
    return registro


def ler(codigo: str) -> list[dict]:
    caminho = PASTA_TESTES / codigo / 'comandos.jsonl'
    if not caminho.is_file():
        return []
    eventos = []
    with open(caminho, encoding='utf-8') as arquivo:
        for linha in arquivo:
            try:
                eventos.append(json.loads(linha))
            except ValueError:
                continue  # linha cortada por uma queda de energia
    return eventos


def tem_t0(codigo: str) -> bool:
    return any(e.get('evento') == 't0' for e in ler(codigo))