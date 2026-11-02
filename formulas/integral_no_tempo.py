from formulas import formula, integral


@formula(
    nome='Integral no tempo',
    descricao='Área sob a curva de uma variável ao longo de todo o registro (regra do trapézio). Precisa da taxa de amostragem.',
    entradas={'valores': 'Variável a integrar'},
    usa_tempo=True,
    exemplo={
        'entradas': {'valores': [0, 10, 10, 0]},
        'taxa_hz': 1,
        'esperado': 20.0,
    },
)
def integral_no_tempo(valores, dt):
    return integral(valores, dt)