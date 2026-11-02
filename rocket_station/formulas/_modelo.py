"""MODELO DE FÓRMULA. Copie este arquivo e preencha. Você só mexe no arquivo novo.

COMO CRIAR UMA FÓRMULA
  1. Copie este arquivo (aqui mesmo, na pasta `formulas`) com um nome novo, em
     minúsculas e com "_" no lugar de espaços. Ex.: `potencia_media.py`.
     O nome do arquivo identifica a fórmula.
  2. Preencha o `@formula(...)` abaixo: cada campo está explicado.
  3. Escreva a função logo embaixo (os nomes dos argumentos têm uma regra, veja abaixo).
  4. Rode `python testar_formulas.py`. Ele encontra a sua fórmula sozinho e confere
     o `exemplo` que você escreveu.
  5. Reinicie o app. A fórmula aparece na lista.
  Nenhum outro arquivo do projeto precisa ser alterado.

REGRA DOS ARGUMENTOS DA FUNÇÃO
  A função recebe, com estes nomes exatos:
    - uma entrada para cada nome em `entradas`   (um array de números do numpy)
    - um valor para cada nome em `parametros`     (um número)
    - `dt`, mas só se usa_tempo=True              (segundos entre duas amostras)
  Se os nomes não baterem, o app diz o que falta ou o que sobra.

DICAS
  - A função devolve UM número.
  - Dados faltando chegam como NaN. Prefira np.nanmax, np.nanmean, np.nansum.
  - Para avisar o usuário de algo (ex.: um parâmetro que falta), use
    `raise ValueError('mensagem clara')`: ela é mostrada como está.
  - Mudou a conta de uma fórmula que já existe? Aumente `versao`.
  - Ferramentas prontas, importáveis de `formulas`:
      integral(y, dt)            integral no tempo (regra do trapézio)
      integral_acumulada(y, dt)  integral acumulada (um array)
      derivada(y, dt)            derivada no tempo (um array)
      media_inicial(y, n)        média das n primeiras amostras (ex.: tara)
"""

import numpy as np

from formulas import formula


@formula(
    # Nome que o usuário vê.
    nome='Exemplo: valor médio',
    # O que a fórmula calcula e que suposições faz. Aparece junto do resultado.
    descricao='Média dos valores de uma variável. Serve só como exemplo.',
    # Variáveis que vêm dos dados: {nome do argumento: descrição para o usuário}.
    entradas={'valores': 'Variável a analisar'},
    # Números que o usuário informa (opcional): {nome: (valor padrão, descrição)}.
    parametros={},
    # Unidade do resultado, só para exibir (opcional).
    unidade='',
    # Mude para True se a fórmula precisa do tempo. Aí a função também recebe `dt`.
    usa_tempo=False,
    # Aumente quando mudar a conta (opcional; começa em '1').
    versao='1',
    # Um exemplo com resposta que você sabe de cabeça. É o que `testar_formulas.py` confere.
    #   entradas:   dados de teste, uma lista de números para cada entrada
    #   parametros: (opcional) valores diferentes dos padrões
    #   taxa_hz:    (só se usa_tempo=True) a taxa de amostragem do exemplo
    #   esperado:   o resultado certo
    exemplo={
        'entradas': {'valores': [2, 4, 6]},
        'esperado': 4.0,
    },
)
def exemplo_valor_medio(valores):
    return np.nanmean(valores)