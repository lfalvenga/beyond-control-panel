from dataclasses import dataclass
from enum import Enum

COUNTDOWN_S = 5.0  # segundos entre apertar IGNIÇÃO e o envio do cmd4
ACK_TIMEOUT_S = 5.0  # depois disso sem ACK: "sem confirmação"
MAX_SILENCE_S = 3.0  # link sem pacotes há mais que isso bloqueia (ou aborta) a ignição

# nomes históricos dos eventos no comandos.jsonl, mantidos por compatibilidade
EV_CMD, EV_ACK, EV_T0 = 'cmd', 'ack', 't0'
EV_COUNTDOWN_STARTED, EV_COUNTDOWN_CANCELLED = 'contagem_iniciada', 'contagem_cancelada'
EV_IGNITION_FAILED, EV_RECORDING_STARTED = 'ignicao_falhou', 'gravacao_iniciada'


class StageState(str, Enum):
    UNKNOWN = 'unknown'  # sem informação do ACK
    OFF = 'off'
    SENT = 'sent'  # enviado, aguardando o ACK
    CONFIRMED = 'confirmed'
    NO_CONFIRMATION = 'no_confirmation'


class TickAction(str, Enum):
    NONE = 'none'
    ABORT = 'abort'
    FIRE = 'fire'


@dataclass(frozen=True)
class LinkSnapshot:
    """O que a máquina de estados precisa saber do mundo, num instante."""

    connected: bool
    acks: dict[int, int]
    recording: bool  # gravando NESTA operação
    silence_s: float | None
    panel_visible: bool = True


@dataclass(frozen=True)
class TickResult:
    action: TickAction = TickAction.NONE
    reason: str = ''


class Activation:
    """Estágios 1 a 3 (armação) e estágio 4 (ignição, com contagem cancelável). Sem I/O."""

    def __init__(self, clock) -> None:
        self._clock = clock
        self._pending: dict[int, float] = {}  # estágio -> instante do envio
        self._countdown_end: float | None = None
        self.countdown_code: str | None = None
        self.ignition_sent = False

    @property
    def counting(self) -> bool:
        return self._countdown_end is not None

    def remaining_s(self) -> float | None:
        return None if self._countdown_end is None else max(0.0, self._countdown_end - self._clock())

    def pending_age(self, n: int) -> float | None:
        sent = self._pending.get(n)
        return None if sent is None else self._clock() - sent

    # ---------- estágios 1 a 3 ----------

    def stage_state(self, n: int, snap: LinkSnapshot) -> StageState:
        ack = snap.acks.get(n)
        if ack == 1:
            return StageState.CONFIRMED
        age = self.pending_age(n)
        if age is not None:
            return StageState.NO_CONFIRMATION if age > ACK_TIMEOUT_S else StageState.SENT
        return StageState.OFF if ack == 0 else StageState.UNKNOWN

    def arm_blocker(self, n: int, snap: LinkSnapshot) -> str:
        if not snap.connected:
            return 'estação desconectada'
        if self.ignition_sent:
            return 'a ignição já foi enviada (desarme para uma nova tentativa)'
        if self.counting:
            return 'contagem de ignição em andamento'
        if snap.acks.get(n) == 1:
            return 'este estágio já está confirmado'
        if n > 1 and snap.acks.get(n - 1) != 1:
            return f'o estágio {n - 1} precisa estar confirmado'
        age = self.pending_age(n)
        if age is not None and age <= ACK_TIMEOUT_S:
            return 'aguardando a confirmação deste estágio'
        return ''

    def mark_sent(self, n: int) -> None:
        self._pending[n] = self._clock()

    def clear_pending(self, n: int) -> None:
        self._pending.pop(n, None)

    # ---------- ignição ----------

    def ignition_blocker(self, snap: LinkSnapshot, in_countdown: bool = False) -> str:
        """Motivo pelo qual a ignição não pode seguir ('' = liberada)."""
        if not snap.connected:
            return 'estação desconectada'
        if not all(snap.acks.get(n) == 1 for n in (1, 2, 3)):
            return 'os estágios 1, 2 e 3 precisam estar confirmados'
        if not snap.recording:
            return 'a gravação não está ativa'
        if snap.silence_s is None or snap.silence_s > MAX_SILENCE_S:
            return 'o link está sem pacotes recentes'
        if in_countdown and not snap.panel_visible:
            return 'o painel de acionamento foi fechado'
        if not in_countdown and self.ignition_sent:
            return 'a ignição já foi enviada (desarme para uma nova tentativa)'
        return ''

    def start_countdown(self, code: str) -> None:
        self._countdown_end = self._clock() + COUNTDOWN_S
        self.countdown_code = code

    def cancel(self) -> bool:
        was_counting = self.counting
        self._countdown_end = None
        return was_counting

    def tick(self, snap: LinkSnapshot) -> TickResult:
        """Chamada a cada instante: aborta a contagem se algo falhou, ou manda disparar."""
        if not self.counting:
            return TickResult()
        reason = self.ignition_blocker(snap, in_countdown=True)
        if reason:
            self._countdown_end = None
            return TickResult(TickAction.ABORT, reason)
        if self._clock() >= self._countdown_end:
            self._countdown_end = None
            return TickResult(TickAction.FIRE)
        return TickResult()

    def mark_ignition_sent(self) -> None:
        self.ignition_sent = True

    def disarm(self) -> bool:
        """Zera tudo (contagem, envios pendentes, ignição enviada). Devolve se havia contagem."""
        was_counting = self.cancel()
        self._pending.clear()
        self.ignition_sent = False
        return was_counting


def describe_event(event: dict) -> str:
    name = event.get('evento')
    if name == EV_CMD:
        return f"cmd{event.get('estagio')}={event.get('valor')} enviado"
    if name == EV_ACK:
        return f"ack{event.get('estagio')}={event.get('valor')}"
    if name == EV_T0:
        return 'T0 definido (primeiro ack3)'
    if name == EV_COUNTDOWN_STARTED:
        return 'contagem iniciada'
    if name == EV_COUNTDOWN_CANCELLED:
        return f"contagem CANCELADA: {event.get('motivo', '')}"
    if name == EV_IGNITION_FAILED:
        return 'FALHA: a ignição não foi enviada'
    if name == EV_RECORDING_STARTED:
        return f"gravação {event.get('gravacao')} iniciada"
    return str(name)