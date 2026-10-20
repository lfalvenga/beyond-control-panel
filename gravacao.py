"""Gravação da telemetria no pacote: registro bruto (.jsonl) e fonte em tabela (.csv)."""

import csv
import json
from datetime import datetime
from pathlib import Path

import fontes
from estacao_solo import RESERVADOS
from telemetria_dados import Telemetria


def nova_gravacao(codigo: str) -> tuple[str, Path]:
    pasta = fontes.pasta_dados(codigo)
    pasta.mkdir(parents=True, exist_ok=True)
    nomes = [f.id for f in fontes.listar_fontes(codigo)] + [p.stem for p in pasta.glob('radio-*.jsonl')]
    numeros = [int(n.split('-')[1]) for n in nomes if n.startswith('radio-') and n.split('-')[1].isdigit()]
    identificador = f'radio-{max(numeros, default=0) + 1:03d}'
    return identificador, pasta / f'{identificador}.jsonl'


def pendentes(codigo: str, ignorar: str = '') -> list[str]:
    """Gravações cujo registro bruto existe, mas que nunca foram finalizadas."""
    pasta = fontes.pasta_dados(codigo)
    if not pasta.is_dir():
        return []
    registradas = {f.id for f in fontes.listar_fontes(codigo)}
    resultado = []
    for arquivo in sorted(pasta.glob('radio-*.jsonl')):
        if arquivo.stem in registradas or arquivo.stem == ignorar:
            continue
        if arquivo.stat().st_size == 0:
            arquivo.unlink()  # gravação que nunca recebeu nada
            continue
        resultado.append(arquivo.stem)
    return resultado


def _colunas_de_exibicao(nomes: list[str], tel: Telemetria) -> list[fontes.Coluna]:
    base = {'t_s': 'Tempo (s)', 'packetN': 'Nº do pacote', 'rssi': 'RSSI (dBm)'}
    for e in tel.esperadas:
        if e.nome:
            texto = e.rotulo or e.nome
            base[e.nome] = f'{texto} ({e.unidade})' if e.unidade else texto
    usados: set[str] = set()
    colunas = []
    for nome in nomes:
        exibicao = base.get(nome, nome)
        if exibicao.lower() in usados:
            exibicao = nome
        if exibicao.lower() in usados:
            exibicao = f'{nome} ({len(usados)})'
        usados.add(exibicao.lower())
        colunas.append(fontes.Coluna(nome, exibicao))
    return colunas


def finalizar(codigo: str, identificador: str, tel: Telemetria) -> fontes.Fonte:
    """Gera a tabela a partir do registro bruto e a registra como fonte do pacote."""
    pasta = fontes.pasta_dados(codigo)
    if identificador in {f.id for f in fontes.listar_fontes(codigo)}:
        raise ValueError('Esta gravação já foi finalizada.')

    registros = []
    with open(pasta / f'{identificador}.jsonl', encoding='utf-8') as arquivo:
        for linha in arquivo:
            try:
                registro = json.loads(linha)
                registros.append((registro['t_s'], registro['msg']))
            except (ValueError, KeyError, TypeError):
                continue  # linha cortada por uma queda de energia: ignora
    if not registros:
        raise ValueError('A gravação está vazia: nenhum pacote foi recebido.')

    variaveis: list[str] = []
    for _, msg in registros:
        for nome in msg:
            if nome not in RESERVADOS and nome not in variaveis:
                variaveis.append(nome)
    do_link = [r for r in ('packetN', 'rssi') if any(r in msg for _, msg in registros)]
    nomes = ['t_s', *do_link, *variaveis]

    def texto(valor):
        if isinstance(valor, bool):
            return str(valor).lower()
        if isinstance(valor, (int, float, str)):
            return valor
        return '' if valor is None else str(valor)

    destino = pasta / f'{identificador}.csv'
    temporario = pasta / f'{identificador}.csv.tmp'
    with open(temporario, 'w', encoding='utf-8', newline='') as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(nomes)
        for t_s, msg in registros:
            escritor.writerow([t_s] + [texto(msg.get(n, '')) for n in nomes[1:]])
    temporario.replace(destino)

    duracao = registros[-1][0] - registros[0][0]
    taxa = (len(registros) - 1) / duracao if len(registros) > 1 and duracao > 0 else None
    fonte = fontes.Fonte(
        id=identificador,
        arquivo=destino.name,
        origem='Telemetria (rádio)',
        importado_em=datetime.now().isoformat(timespec='seconds'),
        separador=',',
        codificacao='utf-8',
        linhas=len(registros),
        colunas=_colunas_de_exibicao(nomes, tel),
        taxa_hz=taxa,
        tipo='radio',
    )
    fontes.adicionar_fonte(codigo, fonte)
    return fonte