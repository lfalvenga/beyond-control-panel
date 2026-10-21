from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / 'data'
OPERATIONS_DIR = DATA_DIR / 'operations'
FORMAT_VERSION = 3  # versão do formato dos arquivos em disco
PACKAGE_EXTENSION = '.beyondtest'
TRASH_DIR_NAME = '.lixeira'  # nome histórico, mantido por compatibilidade