import math
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime

from src.application.ports import CommandLog
from src.application.recording_service import RecordingService
from src.application.telemetry_service import TelemetryService
from src.domain.activation import (
    COUNTDOWN_S,
    EV_ACK,
    EV_CMD,
    EV_COUNTDOWN_CANCELLED,
    EV_COUNTDOWN_STARTED,
    EV_IGNITION_FAILED,
    EV_RECORDING_STARTED,
    EV_T0,
    Activation,
    LinkSnapshot,
    StageState,
    TickAction,
    describe_event,
)


@dataclass(frozen=True)
class Notice:
    text: str
    level: str = 'info'  # 'info', 'warning' ou 'negative'
    persistent: bool = False


@dataclass(frozen=True)
class StageView:
    number: int
    state: StageState
    text: str
    can_arm: bool


@dataclass(frozen=True)
class ActivationView:
    stages: list
    connected: bool
    silence_s: float | None
    counting: bool
    countdown_text: str
    can_ignite: bool
    ignition_blocker: str
    ignition_sent_at: str
    ack4_text: str


class ActivationService:
    def __init__(
        self,
        telemetry: TelemetryService,
        recording: RecordingService,
        log: CommandLog,
        clock=time.monotonic,
    ) -> None:
        self._t = telemetry
        self._r = recording
        self._log = log
        self._a = Activation(clock)
        self._journal: deque = deque(maxlen=200)
        self._journal_count = 0
        self.ignition_sent_at = ''

    # ---------- leitura ----------

    @property
    def journal_count(self) -> int:
        return self._journal_count

    def journal_since(self, seen: int) -> tuple[list[str], int]:
        new = min(self._journal_count - seen, len(self._journal))
        return (list(self._journal)[-new:] if new > 0 else []), self._journal_count

    def history_lines(self, code: str) -> list[str]:
        return [
            f"{str(e.get('t', ''))[11:19]}  {describe_event(e)}" for e in self._log.read(code)[-60:]
        ]

    def view(self, code: str | None, panel_visible: bool = True) -> ActivationView:
        snap = self._snapshot(code, panel_visible)
        stages = []
        for n in (1, 2, 3):
            state = self._a.stage_state(n, snap)
            if state is StageState.CONFIRMED:
                text = f'CONFIRMADO {self._t.acks_at.get(n, "")}'
            elif state is StageState.SENT:
                text = f'enviado, aguardando ({self._a.pending_age(n):.0f} s)'
            elif state is StageState.NO_CONFIRMATION:
                text = 'SEM CONFIRMAÇÃO'
            else:
                text = 'desligado' if state is StageState.OFF else 'sem informação do ACK'
            stages.append(StageView(n, state, text, self._a.arm_blocker(n, snap) == ''))
        counting = self._a.counting
        blocker = '' if counting else self._a.ignition_blocker(snap)
        ack4 = self._t.acks.get(4) == 1
        return ActivationView(
            stages=stages,
            connected=snap.connected,
            silence_s=snap.silence_s,
            counting=counting,
            countdown_text=f'IGNIÇÃO EM {math.ceil(self._a.remaining_s() or 0)}' if counting else '',
            can_ignite=not counting and not blocker,
            ignition_blocker=blocker,
            ignition_sent_at=self.ignition_sent_at,
            ack4_text=f'ack4 recebido às {self._t.acks_at.get(4, "")} (informativo)' if ack4 else '',
        )

    # ---------- ações ----------

    def arm(self, code: str | None, n: int) -> list[Notice]:
        if code is None:
            return [Notice('Escolha uma operação.', 'warning')]
        reason = self._a.arm_blocker(n, self._snapshot(code))
        if reason:
            return [Notice(f'Estágio {n} bloqueado: {reason}.', 'warning')]
        notices: list[Notice] = []
        if n == 3 and not (self._r.recording and self._r.code == code):  # a gravação começa junto do 3º
            if self._r.recording:
                return [Notice(f'Há uma gravação ativa na operação {self._r.code}: finalize-a antes.', 'warning')]
            try:
                recording_id = self._r.start(code)
            except OSError as error:
                return [Notice(
                    f'Não foi possível abrir a gravação ({error}): o 3º estágio NÃO foi armado.', 'negative'
                )]
            notices += self._event(code, EV_RECORDING_STARTED, gravacao=recording_id)
        _, extra = self._send(code, n, 1)
        return notices + extra

    def disarm(self, code: str | None) -> list[Notice]:
        cancelled_code = self._a.countdown_code
        notices: list[Notice] = []
        if self._a.disarm():
            notices += self._cancelled(cancelled_code, 'desarmar tudo', automatic=False)
        self.ignition_sent_at = ''
        for n in (3, 2, 1):
            ok, extra = self._send(code, n, 0)
            notices += extra
            if not ok:
                break
        return notices

    def start_countdown(self, code: str | None, panel_visible: bool = True) -> list[Notice]:
        if self._a.counting:
            return []
        if code is None:
            return [Notice('Escolha uma operação.', 'warning')]
        reason = self._a.ignition_blocker(self._snapshot(code, panel_visible))
        if reason:
            return [Notice(f'Ignição bloqueada: {reason}.', 'warning')]
        self._a.start_countdown(code)
        return self._event(code, EV_COUNTDOWN_STARTED)

    def cancel_countdown(self, reason: str, automatic: bool = False) -> list[Notice]:
        code = self._a.countdown_code
        if not self._a.cancel():
            return []
        return self._cancelled(code, reason, automatic)

    def operation_changed(self) -> list[Notice]:
        code = self._a.countdown_code
        notices = []
        if self._a.disarm():
            notices = self._cancelled(code, 'a operação ativa mudou', automatic=True)
        self.ignition_sent_at = ''
        return notices

    def tick(self, code: str | None, panel_visible: bool = True) -> list[Notice]:
        """Chamada a cada instante (mesmo com o painel fechado): ACKs e contagem."""
        notices = self._process_acks(code)
        result = self._a.tick(self._snapshot(code, panel_visible))
        if result.action is TickAction.ABORT:
            notices += self._cancelled(self._a.countdown_code, result.reason, automatic=True)
        elif result.action is TickAction.FIRE:
            ok, extra = self._send(self._a.countdown_code, 4, 1)  # nunca é reenviado
            notices += extra
            if ok:
                self._a.mark_ignition_sent()
                self.ignition_sent_at = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            else:
                notices += self._event(self._a.countdown_code, EV_IGNITION_FAILED)
        return notices

    # ---------- internos ----------

    def _snapshot(self, code: str | None, panel_visible: bool = True) -> LinkSnapshot:
        return LinkSnapshot(
            connected=self._t.connected,
            acks=dict(self._t.acks),
            recording=self._r.recording and code is not None and self._r.code == code,
            silence_s=self._t.seconds_since_last_packet,
            panel_visible=panel_visible,
        )

    def _note(self, text: str) -> None:
        self._journal.append(f'{datetime.now():%H:%M:%S}  {text}')
        self._journal_count += 1

    def _event(self, code: str | None, name: str, **data) -> list[Notice]:
        if code is None:
            return []
        if self._r.recording and self._r.code == code:  # liga o evento ao tempo da gravação
            data.setdefault('gravacao', self._r.recording_id)
            data.setdefault('t_s', round(self._r.elapsed_s(), 3))
        event = {'evento': name, **data}
        self._note(describe_event(event))
        try:
            self._log.append(code, event)
        except OSError as error:
            return [Notice(f'Não foi possível registrar no histórico: {error}', 'warning')]
        return []

    def _send(self, code: str | None, n: int, value: int) -> tuple[bool, list[Notice]]:
        try:
            self._t.send({f'cmd{n}': value})
        except ConnectionError as error:
            self._note(f'FALHA ao enviar cmd{n}={value}: {error}')
            return False, [Notice(str(error), 'negative')]
        if value == 1 and n <= 3:
            self._a.mark_sent(n)
        return True, self._event(code, EV_CMD, estagio=n, valor=value)

    def _cancelled(self, code: str | None, reason: str, automatic: bool) -> list[Notice]:
        notices = self._event(code, EV_COUNTDOWN_CANCELLED, motivo=reason, automatico=automatic)
        notices.append(Notice(f'Contagem cancelada: {reason}', 'negative' if automatic else 'warning'))
        return notices

    def _process_acks(self, code: str | None) -> list[Notice]:
        notices: list[Notice] = []
        while self._t.ack_changes:
            n, previous, value = self._t.ack_changes.pop(0)
            notices += self._event(code, EV_ACK, estagio=n, valor=value)
            if value == 1:
                self._a.clear_pending(n)
                if n == 3 and code is not None and not any(
                    e.get('evento') == EV_T0 for e in self._log.read(code)
                ):
                    notices += self._event(code, EV_T0)
            if previous == 1 and value == 0 and n in (1, 2, 3):
                notices.append(Notice(f'ALERTA: o estágio {n} voltou a 0.', 'negative', persistent=True))
        return notices