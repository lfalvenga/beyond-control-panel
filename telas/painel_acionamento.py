import math
import time
from datetime import datetime

from nicegui import ui

import comandos
import gravacao
from estacao_solo import estacao
from estado import estado
from telas.estacao import AMARELO, ATRASO_AMARELO, CINZA, VERDE, VERMELHO

CONTAGEM_S = 5.0  # segundos entre apertar IGNIÇÃO e o envio do cmd4
TEMPO_ACK_S = 5.0  # depois disso sem ACK: "sem confirmação"


def montar(painel_visivel) -> None:
    """Painel de acionamento (numa gaveta à direita, só na Telemetria). painel_visivel() diz se está aberto."""
    s = {'pendentes': {}, 'contagem_fim': None, 'cod_contagem': None, 'ignicao_em': None}
    w: dict = {}

    def anotar(texto: str) -> None:
        w['log'].push(f'{datetime.now():%H:%M:%S}  {texto}')

    def registrar(evento: str, cod: str | None = None, **dados) -> None:
        cod = cod or estado.teste_ativo
        if cod is None:
            return
        try:
            comandos.registrar(cod, evento, **dados)
        except OSError as erro:
            ui.notify(f'Não foi possível registrar no histórico: {erro}', type='warning')

    def enviar_cmd(n: int, valor: int, cod: str | None = None) -> bool:
        try:
            estacao.enviar({f'cmd{n}': valor})
        except ConnectionError as erro:
            ui.notify(str(erro), type='negative')
            anotar(f'FALHA ao enviar cmd{n}={valor}: {erro}')
            return False
        registrar('cmd', cod, estagio=n, valor=valor)
        anotar(f'cmd{n}={valor} enviado')
        return True

    # ---------- armar e desarmar ----------

    def armar(n: int) -> None:
        cod = estado.teste_ativo
        if cod is None or not estacao.conectada:
            ui.notify('Conecte a estação e escolha uma operação.', type='warning')
            return
        if n == 3 and not estacao.gravando:  # a gravação começa junto do 3º estágio
            try:
                identificador, caminho = gravacao.nova_gravacao(cod)
                estacao.iniciar_gravacao(caminho, cod, identificador)
            except OSError as erro:
                ui.notify(
                    f'Não foi possível abrir a gravação ({erro}): o 3º estágio NÃO foi armado.',
                    type='negative',
                )
                return
            registrar('gravacao_iniciada', gravacao=identificador)
            anotar(f'gravação {identificador} iniciada')
        if enviar_cmd(n, 1):
            s['pendentes'][n] = time.monotonic()

    def desarmar() -> None:
        cancelar_contagem('desarmar tudo')
        for n in (3, 2, 1):
            if not enviar_cmd(n, 0):
                break
        s['pendentes'].clear()
        s['ignicao_em'] = None

    # ---------- ignição ----------

    def bloqueio(em_contagem: bool = False) -> str:
        """Motivo pelo qual a ignição não pode seguir ('' = liberada)."""
        if not estacao.conectada:
            return 'estação desconectada'
        if not all(estacao.acks.get(n) == 1 for n in (1, 2, 3)):
            return 'os estágios 1, 2 e 3 precisam estar confirmados'
        if not estacao.gravando:
            return 'a gravação não está ativa'
        atraso = estacao.sem_pacote_ha
        if atraso is None or atraso > ATRASO_AMARELO:
            return 'o link está sem pacotes recentes'
        if em_contagem and not painel_visivel():
            return 'o painel de acionamento foi fechado'
        if not em_contagem and s['ignicao_em'] is not None:
            return 'a ignição já foi enviada (desarme para uma nova tentativa)'
        return ''

    def iniciar_contagem() -> None:
        if s['contagem_fim'] is not None:
            return
        motivo = bloqueio()
        if motivo:
            ui.notify(f'Ignição bloqueada: {motivo}.', type='warning')
            return
        s['contagem_fim'] = time.monotonic() + CONTAGEM_S
        s['cod_contagem'] = estado.teste_ativo
        registrar('contagem_iniciada', s['cod_contagem'])
        anotar(f'contagem de {CONTAGEM_S:.0f} s iniciada')

    def cancelar_contagem(motivo: str, automatico: bool = False) -> None:
        if s['contagem_fim'] is None:
            return
        s['contagem_fim'] = None
        registrar('contagem_cancelada', s['cod_contagem'], motivo=motivo, automatico=automatico)
        anotar(f'contagem CANCELADA: {motivo}')
        ui.notify(f'Contagem cancelada: {motivo}', type='negative' if automatico else 'warning')

    def enviar_ignicao() -> None:
        cod = s['cod_contagem']
        s['contagem_fim'] = None
        if enviar_cmd(4, 1, cod):  # nunca é reenviado
            s['ignicao_em'] = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        else:
            registrar('ignicao_falhou', cod)

    def ao_mudar_operacao() -> None:
        cancelar_contagem('a operação ativa mudou', automatico=True)
        s['pendentes'].clear()
        s['ignicao_em'] = None

    # ---------- atualização periódica ----------

    def texto_estagio(n: int) -> tuple[str, str]:
        ack = estacao.acks.get(n)
        enviado = s['pendentes'].get(n)
        if ack == 1:
            return f'CONFIRMADO {estacao.acks_em.get(n, "")}', VERDE
        if enviado is not None:
            espera = time.monotonic() - enviado
            if espera > TEMPO_ACK_S:
                return 'SEM CONFIRMAÇÃO', VERMELHO
            return f'enviado, aguardando ({espera:.0f} s)', AMARELO
        if ack == 0:
            return 'desligado', CINZA
        return 'sem informação do ACK', CINZA

    def tique() -> None:
        cod = estado.teste_ativo
        while estacao.mudancas_ack:  # confirmações que chegaram
            n, anterior, valor = estacao.mudancas_ack.pop(0)
            registrar('ack', estagio=n, valor=valor)
            anotar(f'ack{n}={valor}')
            if valor == 1:
                s['pendentes'].pop(n, None)
                if n == 3 and cod is not None and not comandos.tem_t0(cod):
                    registrar('t0')
                    anotar('T0 definido (primeiro ack3)')
            if anterior == 1 and valor == 0 and n in (1, 2, 3):
                ui.notify(f'ALERTA: o estágio {n} voltou a 0.', type='negative', timeout=0, close_button='OK')

        agora = time.monotonic()
        em_contagem = s['contagem_fim'] is not None
        if em_contagem:
            motivo = bloqueio(em_contagem=True)
            if motivo:
                cancelar_contagem(motivo, automatico=True)
                em_contagem = False
            elif agora >= s['contagem_fim']:
                enviar_ignicao()
                em_contagem = False

        conectada = estacao.conectada
        w['operacao'].set_text(f'Operação: {cod or "—"}')
        atraso = estacao.sem_pacote_ha if conectada else None
        w['link'].set_text('Estação desconectada' if not conectada else
                           'Último pacote há —' if atraso is None else f'Último pacote há {atraso:.1f} s')
        w['link'].classes(replace='text-sm ' + (CINZA if atraso is None else VERDE if atraso <= ATRASO_AMARELO else VERMELHO))

        for n in (1, 2, 3):
            texto, cor = texto_estagio(n)
            w[f'estado{n}'].set_text(texto)
            w[f'estado{n}'].classes(replace=f'text-sm {cor}')
            enviado = s['pendentes'].get(n)
            livre = enviado is None or agora - enviado > TEMPO_ACK_S
            anterior_ok = n == 1 or estacao.acks.get(n - 1) == 1
            w[f'botao{n}'].set_enabled(
                conectada and estacao.acks.get(n) != 1 and anterior_ok and livre
                and s['ignicao_em'] is None and not em_contagem
            )
        w['desarmar'].set_enabled(conectada)

        motivo = '' if em_contagem else bloqueio()
        w['ignicao'].set_enabled(not em_contagem and not motivo)
        w['motivo'].set_text('' if em_contagem or not motivo else f'Bloqueada: {motivo}.')
        w['contagem'].set_visibility(em_contagem)
        w['cancelar'].set_visibility(em_contagem)
        if em_contagem:
            w['contagem'].set_text(f'IGNIÇÃO EM {math.ceil(s["contagem_fim"] - agora)}')

        w['ignicao_enviada'].set_text(
            f'IGNIÇÃO ENVIADA às {s["ignicao_em"]}' if s['ignicao_em'] else ''
        )
        if estacao.acks.get(4) == 1:
            w['ack4'].set_text(f'ack4 recebido às {estacao.acks_em.get(4, "")} (informativo)')
        else:
            w['ack4'].set_text('')

    # ---------- interface ----------

    ui.label('ACIONAMENTO').classes('text-xl font-bold tracking-widest')
    w['operacao'] = ui.label('').classes('text-gray-400 text-sm')
    w['link'] = ui.label('').classes('text-sm')
    ui.separator()

    for n in (1, 2, 3):
        with ui.card().classes('w-full'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label(f'Estágio {n}').classes('font-bold')
                w[f'estado{n}'] = ui.label('').classes('text-sm')
            w[f'botao{n}'] = ui.button(f'Armar {n}', on_click=lambda n=n: armar(n)).classes('w-full')
    w['desarmar'] = ui.button('Desarmar tudo', on_click=desarmar).props('outline color=orange').classes('w-full')

    ui.separator()
    w['ignicao'] = ui.button('IGNIÇÃO', on_click=iniciar_contagem, color='negative').classes('w-full text-xl')
    w['motivo'] = ui.label('').classes('text-gray-400 text-sm')
    w['contagem'] = ui.label('').classes('text-3xl font-bold text-red-400 w-full text-center')
    w['cancelar'] = ui.button(
        'CANCELAR (Esc)', on_click=lambda: cancelar_contagem('cancelado pelo operador'), color='warning'
    ).classes('w-full text-2xl')
    w['ignicao_enviada'] = ui.label('').classes('text-red-400 font-bold')
    w['ack4'] = ui.label('').classes('text-gray-400 text-sm')

    ui.separator()
    ui.label('Eventos').classes('font-bold')
    w['log'] = ui.log(max_lines=60).classes('w-full h-40')

    ui.keyboard(
        on_key=lambda e: cancelar_contagem('cancelado pelo operador (Esc)')
        if e.key.escape and e.action.keydown else None
    )
    estado.ao_mudar_ativo(ao_mudar_operacao)
    ui.timer(0.1, tique)