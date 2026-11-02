# Beyond Static Fire

Aplicativo desktop para testes estáticos e voos: cadastro, acionamento, telemetria, log do SD e relatório.

## Rodar

```
pip install -r requirements.txt
python app.py
python -m pytest
```

## Estrutura

- `src/domain`: regras e entidades (sem arquivo, serial ou tela)
- `src/application`: casos de uso (serviços) e interfaces (`ports.py`)
- `src/infrastructure`: disco e porta serial
- `src/ui`: telas NiceGUI (só desenham e chamam os serviços)
- `formulas/`: fórmulas de cálculo. Para criar uma, copie `_modelo.py`. Nenhum outro arquivo muda.
- `data/operations/`: os dados (fora do git)