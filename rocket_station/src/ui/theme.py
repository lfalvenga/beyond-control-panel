"""Tema visual: paleta, tipografia e CSS global. Mude aqui para mudar o app inteiro."""

from nicegui import ui

# Paleta estimada a partir dos designs da equipe (ajuste os hexadecimais aqui)
PALETTE = {
    'bg': '#EEF3F5',  # fundo da área de conteúdo
    'card': '#FFFFFF',
    'line': '#D9E2E7',  # bordas
    'ink': '#0B1220',  # títulos
    'text': '#1E293B',
    'muted': '#64748B',
    'nav': '#102A3A',  # menu lateral
    'nav-active': '#1B4258',
    'nav-text': '#E6EEF2',
    'nav-muted': '#8FA7B5',
    'accent': '#E2572B',  # laranja da marca
    'primary': '#0F4C66',
    'ok': '#157F5B',
    'ok-bg': '#D9F2E6',
    'warn': '#B7791F',
    'warn-bg': '#FDF1D6',
    'bad': '#C0392B',
    'bad-bg': '#F8D7DC',
}

# classes de texto usadas pelas telas (legíveis em fundo claro)
GRAY, GREEN, YELLOW, RED = 'text-slate-500', 'text-emerald-700', 'text-amber-600', 'text-red-600'


def higher_is_better(value: float | None, green: float, yellow: float) -> str:
    if value is None:
        return GRAY
    return GREEN if value >= green else YELLOW if value >= yellow else RED


def lower_is_better(value: float | None, green: float, yellow: float) -> str:
    if value is None:
        return GRAY
    return GREEN if value <= green else YELLOW if value <= yellow else RED


CSS = """
@font-face {
  font-family: 'Inter';
  src: url('/assets/fonts/Inter.ttf') format('truetype');
  font-weight: 100 900;
  font-display: swap;
}
body { background: var(--bg); color: var(--text);
       font-family: 'Inter', system-ui, 'Segoe UI', sans-serif; }
.nicegui-content { padding: 28px 36px; gap: 18px; }

/* componentes */
.q-card { border-radius: 20px; box-shadow: none !important; border: 1px solid var(--line); }
.q-btn { border-radius: 12px; text-transform: none; font-weight: 600; letter-spacing: 0; }
.q-field--outlined .q-field__control { border-radius: 14px; }
.q-field__label { font-size: .8rem; letter-spacing: .02em; }
.text-4xl { color: var(--ink); font-weight: 800; letter-spacing: -.02em; }
.text-2xl { color: var(--ink); font-weight: 700; }

/* classes antigas das telas, remapeadas para a paleta */
.text-gray-400 { color: var(--muted) !important; }
.text-green-400 { color: var(--ok) !important; }
.text-yellow-400, .text-orange-400 { color: var(--warn) !important; }
.text-red-400 { color: var(--bad) !important; }

/* menu lateral */
.nav-drawer { background: var(--nav) !important; color: var(--nav-text); }
.nav-drawer .q-item { border-radius: 12px; margin: 2px 0; min-height: 40px; color: var(--nav-text); }
.nav-drawer .text-gray-400, .nav-label { color: var(--nav-muted) !important; }
.nav-active { background: var(--nav-active) !important; color: #fff !important; }
.nav-label { font-size: .7rem; letter-spacing: .3em; text-transform: uppercase; }
.drawer-light { background: var(--bg) !important; }

/* cabeçalho */
.crumb { font-size: .72rem; font-weight: 700; letter-spacing: .25em; text-transform: uppercase;
         color: var(--muted); }
.stamp { font-size: .72rem; font-weight: 600; letter-spacing: .25em; color: var(--muted); }
.chip { padding: 6px 18px; border-radius: 999px; font-weight: 700; font-size: .9rem; }
.chip-ok { background: var(--ok-bg); color: var(--ok); }
.chip-off { background: #E2E8F0; color: var(--muted); }
.chip-bad { background: var(--bad-bg); color: var(--bad); }
"""


def apply_theme() -> None:
    ui.colors(
        primary=PALETTE['primary'],
        secondary=PALETTE['nav'],
        accent=PALETTE['accent'],
        positive=PALETTE['ok'],
        negative=PALETTE['bad'],
        warning=PALETTE['warn'],
        info=PALETTE['primary'],
    )
    variables = ':root{' + ''.join(f'--{key}:{value};' for key, value in PALETTE.items()) + '}'
    ui.add_css(variables + CSS)