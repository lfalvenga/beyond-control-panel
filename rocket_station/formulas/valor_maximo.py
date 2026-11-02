import numpy as np

from formulas import formula


@formula(
    nome='Valor máximo',
    descricao='Maior valor de uma variável.',
    entradas={'valores': 'Variável a analisar'},
    exemplo={
        'entradas': {'valores': [1, 5, 3]},
        'esperado': 5.0,
    },
)
def valor_maximo(valores):
    return np.nanmax(valores)