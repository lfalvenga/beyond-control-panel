"""Funções prontas para escrever fórmulas. Tudo aqui trabalha com arrays do numpy.

Lacunas nos dados chegam às fórmulas como NaN, e as funções abaixo as ignoram.
"""

import numpy as np


def integral(y, dt: float) -> float:
    """Integral de y no tempo pela regra do trapézio. `dt` é o intervalo entre amostras (s).

    Intervalos que tocam uma lacuna (NaN) não contribuem para o resultado.
    """
    y = np.asarray(y, dtype=float)
    if y.size < 2:
        return 0.0
    trapezios = (y[1:] + y[:-1]) / 2.0 * dt
    return float(np.nansum(trapezios))


def integral_acumulada(y, dt: float):
    """Integral acumulada de y no tempo. Devolve um array do mesmo tamanho (começa em 0)."""
    y = np.asarray(y, dtype=float)
    if y.size < 2:
        return np.zeros_like(y)
    trapezios = (y[1:] + y[:-1]) / 2.0 * dt
    return np.concatenate(([0.0], np.nancumsum(trapezios)))


def derivada(y, dt: float):
    """Derivada de y no tempo (diferenças centrais). Devolve um array do mesmo tamanho."""
    return np.gradient(np.asarray(y, dtype=float), dt)


def media_inicial(y, n: int) -> float:
    """Média das primeiras `n` amostras. Útil para medir o zero (tara) antes do teste."""
    n = int(n)
    if n < 1:
        raise ValueError('A quantidade de amostras deve ser pelo menos 1.')
    return float(np.nanmean(np.asarray(y, dtype=float)[:n]))