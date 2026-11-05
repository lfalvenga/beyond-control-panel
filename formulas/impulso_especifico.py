from formulas import formula, integral


@formula(
    nome='Impulso específico',
    descricao='Impulso total (integral do empuxo) dividido pelo peso do propelente (m · g).',
    entradas={'empuxo': 'Empuxo (N)'},
    parametros={
        'massa_propelente': (1.0, 'Massa de propelente (kg)'),
        'g': (9.80665, 'Aceleração da gravidade (m/s²)'),
    },
    unidade='s',
    usa_tempo=True,
    exemplo={
        'entradas': {'empuxo': [100, 100, 100]},
        'parametros': {'massa_propelente': 2.0, 'g': 10.0},
        'taxa_hz': 1,
        'esperado': 10.0,  # integral = 200 N·s; 200 / (2 · 10) = 10 s
    },
)
def impulso_especifico(empuxo, dt, massa_propelente, g):
    return integral(empuxo, dt) / (massa_propelente * g)