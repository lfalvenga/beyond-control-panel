"""Conexão com a estação de solo: lê linhas JSON pela serial (ou de uma fonte simulada)."""

import json
import math
import queue
import random
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

import serial
import serial.tools.list_ports

SIMULADA = 'simulada'
JANELA_PACOTES = 30  # quantos pacotes recentes entram no cálculo da taxa de entrega
HISTORICO_MAX = 100_000
RESERVADOS = ('rssi', 'packetN', 'ack1', 'ack2', 'ack3', 'ack4')  # informações do link e da armação

@dataclass
class Variavel:
    nome: str
    valor: object = None
    numerica: bool = False
    atualizada_em: float = 0.0  # time.monotonic()
    contagem: int = 0


def _numero(valor) -> float | None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return float(valor) if math.isfinite(valor) else None


class EstacaoSolo:
    def __init__(self) -> None:
        self._fila: queue.Queue = queue.Queue()
        self._parar = threading.Event()
        self._leitor: threading.Thread | None = None
        self.conectada = False
        self.fonte = ''
        self.erro = ''
        self._gravacao = None  # arquivo aberto durante a gravação
        self.gravacao_codigo = ''
        self.gravacao_ident = ''
        self.gravacao_inicio = 0.0
        self.gravados = 0
        self._porta = None  # a porta serial aberta (para enviar comandos)
        self._zerar()

    def _zerar(self) -> None:
        self.recebidos = 0  # pacotes de dados válidos
        self.invalidos = 0  # linhas que não são JSON, ou estão malformadas
        self.ignoradas = 0  # mensagens de tipo desconhecido (ex.: ack, tratado em outro lugar)
        self.rssi: float | None = None
        self.ultimo_pacote: float | None = None
        self.variaveis: dict[str, Variavel] = {}
        self._seqs: deque = deque(maxlen=JANELA_PACOTES)
        self.historico: deque = deque(maxlen=HISTORICO_MAX)  # (s desde a conexão, seq, {variável: valor})
        self._inicio = time.monotonic()
        self.acks: dict[int, int] = {}  # último ackN recebido (ausente = sem informação)
        self.acks_em: dict[int, str] = {}  # horário em que cada ackN passou a 1
        self.mudancas_ack: list = []  # (n, valor anterior, valor novo), consumidas pelo painel

    # ---------- conexão ----------

    @staticmethod
    def portas() -> list[tuple[str, str]]:
        return [
            (p.device, f'{p.device} · {p.description}')
            for p in serial.tools.list_ports.comports()
        ]

    def conectar(self, fonte: str, baud: int = 115200) -> None:
        self.desconectar()
        while not self._fila.empty():
            self._fila.get_nowait()
        self._zerar()
        self.erro = ''
        self.fonte = fonte
        self._parar = threading.Event()
        alvo = self._ler_simulada if fonte == SIMULADA else self._ler_serial
        self._leitor = threading.Thread(target=alvo, args=(self._parar, fonte, baud), daemon=True)
        self._leitor.start()
        self.conectada = True

    def desconectar(self) -> None:
        self._parar.set()
        if self._leitor is not None and self._leitor.is_alive():
            self._leitor.join(timeout=1.5)
        self._leitor = None
        self.conectada = False

    def _ler_serial(self, parar: threading.Event, porta: str, baud: int) -> None:
        try:
            with serial.Serial(porta, baud, timeout=0.5) as conexao:
                self._porta = conexao
                buffer = b''
                while not parar.is_set():
                    pedaco = conexao.readline()
                    if not pedaco:
                        continue
                    buffer += pedaco
                    if len(buffer) > 65536:  # lixo sem fim de linha: descarta
                        buffer = b''
                        continue
                    if not buffer.endswith(b'\n'):
                        continue  # linha ainda incompleta
                    linha = buffer.decode('utf-8', errors='replace').strip()
                    buffer = b''
                    if linha:
                        self._fila.put(('linha', linha))
        except (serial.SerialException, OSError) as erro:
            if not parar.is_set():
                self._fila.put(('erro', str(erro)))
        finally:
            self._porta = None
    def _ler_simulada(self, parar: threading.Event, _fonte: str, _baud: int) -> None:
        """Gera linhas como a estação geraria: perdas, campos que aparecem e somem, ruído."""
        inicio = time.monotonic()
        seq = 0
        while not parar.is_set():
            seq += 1
            t = time.monotonic() - inicio
            if seq % 50 == 0:
                self._fila.put(('linha', 'ruído na linha {{'))  # linha inválida
            if seq % 70 == 0:
                self._fila.put(('linha', json.dumps({'v': 1, 'tipo': 'status', 'ok': True})))
            if random.random() > 0.12:  # ~12% de perda: o número sequencial pula
                dados = {
                    'empuxo': round(max(0.0, 800 * math.sin(t / 3) ** 2 + random.gauss(0, 5)), 1),
                    'pressao': round(30 + 5 * math.sin(t / 2) + random.gauss(0, 0.2), 2),
                }
                if t > 8:
                    dados['temperatura'] = round(24 + t * 0.05, 1)  # aparece depois de 8 s
                if 20 < t % 30 < 25:
                    del dados['pressao']  # some por uns segundos
                mensagem = {
                    'v': 1,
                    'tipo': 'dados',
                    'link': {'rssi': round(-92 + 14 * math.sin(t / 15) + random.gauss(0, 1), 0), 'seq': seq},
                    'dados': dados,
                }
                self._fila.put(('linha', json.dumps(mensagem)))
            parar.wait(0.1)  # 10 Hz

    # ---------- interpretação ----------

    def processar(self) -> list[str]:
        """Consome o que chegou, atualiza o estado e devolve as linhas brutas (para o monitor)."""
        brutas = []
        while True:
            try:
                tipo, conteudo = self._fila.get_nowait()
            except queue.Empty:
                break
            if tipo == 'erro':
                self.erro = f'Conexão perdida: {conteudo}'
                self.conectada = False
            else:
                brutas.append(conteudo)
                self._tratar(conteudo)
        return brutas

    def _tratar(self, linha: str) -> None:
        try:
            mensagem = json.loads(linha)
        except ValueError:
            self.invalidos += 1
            return
        if not isinstance(mensagem, dict):
            self.invalidos += 1
            return

        agora = time.monotonic()
        self.recebidos += 1
        self.ultimo_pacote = agora
        self.rssi = _numero(mensagem.get('rssi'))
        seq = mensagem.get('packetN')
        self._registrar_seq(seq)
        for n in (1, 2, 3, 4):
            valor_ack = _numero(mensagem.get(f'ack{n}'))
            if valor_ack is not None:
                self._registrar_ack(n, int(valor_ack))
        numericos = {}
        for nome, valor in mensagem.items():
            if nome in RESERVADOS:
                continue
            variavel = self.variaveis.setdefault(str(nome), Variavel(str(nome)))
            numero = _numero(valor)
            variavel.numerica = numero is not None
            variavel.valor = numero if numero is not None else valor
            variavel.atualizada_em = agora
            variavel.contagem += 1
            if numero is not None:
                numericos[str(nome)] = numero
        seq_valida = seq if isinstance(seq, int) and not isinstance(seq, bool) else None
        self.historico.append((agora - self._inicio, seq_valida, numericos))

        if self._gravacao is not None:  # registro bruto: o que chegou e quando
            try:
                registro = {'t_s': round(agora - self.gravacao_inicio, 3), 'msg': mensagem}
                self._gravacao.write(json.dumps(registro, ensure_ascii=False) + '\n')
                self._gravacao.flush()
                self.gravados += 1
            except OSError as erro:
                self.erro = f'Falha ao gravar: {erro}'
                self.parar_gravacao()

    def _registrar_ack(self, n: int, valor: int) -> None:
        anterior = self.acks.get(n)
        self.acks[n] = valor
        if anterior != valor and not (anterior is None and valor == 0):
            if valor == 1:
                self.acks_em[n] = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            self.mudancas_ack.append((n, anterior, valor))

    def enviar(self, mensagem: dict) -> None:
        """Envia uma linha JSON para a estação. Levanta ConnectionError se não conseguir."""
        porta = self._porta
        if not self.conectada or porta is None:
            raise ConnectionError('A estação não está conectada.')
        try:
            porta.write((json.dumps(mensagem, separators=(',', ':')) + '\n').encode('utf-8'))
            porta.flush()
        except (serial.SerialException, OSError) as erro:
            raise ConnectionError(f'Falha ao enviar: {erro}') from erro
    
    def _registrar_seq(self, seq) -> None:
        if isinstance(seq, bool) or not isinstance(seq, int):
            return
        if self._seqs and seq <= self._seqs[-1]:
            self._seqs.clear()  # o contador voltou ao início (volta a zero, ou a estação reiniciou)
        self._seqs.append(seq)

    # ---------- indicadores ----------

    @property
    def entrega(self) -> float | None:
        """% de pacotes recebidos entre os últimos, pela contagem do número sequencial."""
        if len(self._seqs) < 2:
            return None
        esperados = self._seqs[-1] - self._seqs[0] + 1
        return 100.0 * len(self._seqs) / esperados

    @property
    def sem_pacote_ha(self) -> float | None:
        if self.ultimo_pacote is None:
            return None
        return time.monotonic() - self.ultimo_pacote

    def pontos(self, y: str, x: str, janela_s: float | None, maximo: int = 2000) -> list:
        """Pares [x, y] para um gráfico. x: 'tempo', 'seq' ou o nome de outra variável."""
        if not self.historico:
            return []
        corte = self.historico[-1][0] - janela_s if janela_s else None
        encontrados = []
        for t, seq, dados in reversed(self.historico):  # do mais novo para o mais antigo
            if corte is not None and t < corte:
                break
            valor_y = dados.get(y)
            valor_x = t if x == 'tempo' else seq if x == 'seq' else dados.get(x)
            if valor_y is not None and valor_x is not None:
                encontrados.append([valor_x, valor_y])
        encontrados.reverse()
        passo = math.ceil(len(encontrados) / maximo)
        if passo > 1:  # muitos pontos: reduz só a exibição, sempre mantendo o último
            reduzidos = encontrados[::passo]
            if reduzidos[-1] is not encontrados[-1]:
                reduzidos.append(encontrados[-1])
            return reduzidos
        return encontrados

    def iniciar_gravacao(self, caminho: Path, codigo: str, identificador: str) -> None:
        self.parar_gravacao()
        self._gravacao = open(caminho, 'a', encoding='utf-8')
        self.gravacao_codigo = codigo
        self.gravacao_ident = identificador
        self.gravacao_inicio = time.monotonic()
        self.gravados = 0

    def parar_gravacao(self) -> None:
        if self._gravacao is not None:
            self._gravacao.close()
            self._gravacao = None

    @property
    def gravando(self) -> bool:
        return self._gravacao is not None


estacao = EstacaoSolo()