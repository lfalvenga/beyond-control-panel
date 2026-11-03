from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / 'data'
OPERATIONS_DIR = DATA_DIR / 'operations'
EXAMPLES_DIR = DATA_DIR / 'examples'
FORMAT_VERSION = 4  # versão do formato dos arquivos em disco
PACKAGE_EXTENSION = '.beyondtest'
TRASH_DIR_NAME = '.lixeira'  # nome histórico, mantido por compatibilidade

# Limites das faixas de cor da Conexão (ajuste aqui)
RSSI_GREEN_DBM, RSSI_YELLOW_DBM = -90.0, -105.0  # maior é melhor
DELIVERY_GREEN_PCT, DELIVERY_YELLOW_PCT = 90.0, 70.0  # maior é melhor
SILENCE_GREEN_S, SILENCE_YELLOW_S = 1.0, 3.0  # segundos sem pacote: menor é melhor
BAUD_RATES = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]

ASSETS_DIR = ROOT_DIR / 'assets'
