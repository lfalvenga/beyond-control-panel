# Beyond Static Fire

Aplicativo desktop para testes estáticos e voos: cadastro, acionamento, telemetria, log do SD e relatório.

## Rodar

```
pip install -r requirements.txt
python app.py
python -m pytest
```

## Estrutura

- `rocket_station/domain`: regras e entidades (sem arquivo, serial ou tela)
- `rocket_station/application`: casos de uso (serviços) e interfaces (`ports.py`)
- `rocket_station/infrastructure`: disco e porta serial
- `rocket_station/presentation`: telas NiceGUI (só desenham e chamam os serviços)
- `formulas/`: fórmulas de cálculo. Para criar uma, copie `_modelo.py`. Nenhum outro arquivo muda.
- `data/operations/`: os dados (fora do git)