import csv
import io
import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
import math
from functools import lru_cache

from armazenamento import PASTA_TESTES

TAMANHO_MAXIMO = 50 * 1024 * 1024  # 50 MB
LIMITE_LINHAS_TABELA = 5000
SEPARADORES = (',', ';', '\t')


@dataclass
class Coluna:
    original: str  # como está no cabeçalho do CSV
    exibicao: str  # como o usuário quer ver


@dataclass
class Fonte:
    id: str
    arquivo: str
    origem: str
    importado_em: str
    separador: str
    codificacao: str
    linhas: int
    colunas: list[Coluna] = field(default_factory=list)
    taxa_hz: float | None = None  # amostras por segundo com que o SD gravou (opcional)
    tipo: str = 'sd'  # 'sd' (CSV importado) ou 'radio' (telemetria gravada)


@dataclass
class Previa:
    colunas: list[str]
    linhas: list[list[str]]  # só as primeiras
    total_linhas: int
    separador: str
    codificacao: str


# ---------- leitura do CSV ----------


def _decodificar(caminho: Path) -> tuple[str, str]:
    if caminho.stat().st_size > TAMANHO_MAXIMO:
        raise ValueError('Arquivo grande demais (o limite é 50 MB).')
    bruto = caminho.read_bytes()
    try:
        return bruto.decode('utf-8-sig'), 'utf-8-sig'
    except UnicodeDecodeError:
        return bruto.decode('latin-1'), 'latin-1'


def _detectar_separador(texto: str) -> str:
    primeira = next((linha for linha in texto.splitlines() if linha.strip()), '')
    return max(SEPARADORES, key=primeira.count)  # empate ou nenhum: vírgula


def _parece_numero(texto: str) -> bool:
    try:
        float(texto.replace(',', '.'))
        return True
    except ValueError:
        return False


def _nomes_unicos(nomes: list[str]) -> list[str]:
    vistos: dict[str, int] = {}
    resultado = []
    for i, nome in enumerate(nomes):
        base = nome or f'coluna_{i + 1}'
        vistos[base] = vistos.get(base, 0) + 1
        resultado.append(base if vistos[base] == 1 else f'{base}_{vistos[base]}')
    return resultado


def _ajustar(linha: list[str], n: int) -> list[str]:
    return (linha + [''] * n)[:n]


def _separar(texto: str, separador: str) -> tuple[list[str], list[list[str]]]:
    leitor = csv.reader(io.StringIO(texto, newline=''), delimiter=separador)
    linhas = [linha for linha in leitor if any(c.strip() for c in linha)]
    if not linhas:
        raise ValueError('O arquivo está vazio.')
    primeira = [c.strip() for c in linhas[0]]
    if all(_parece_numero(c) for c in primeira if c):
        raise ValueError('O arquivo precisa ter uma linha de cabeçalho com os nomes das variáveis.')
    return _nomes_unicos(primeira), linhas[1:]


def ler_previa(caminho: Path, max_linhas: int = 10) -> Previa:
    texto, codificacao = _decodificar(caminho)
    separador = _detectar_separador(texto)
    colunas, linhas = _separar(texto, separador)
    return Previa(
        colunas=colunas,
        linhas=[_ajustar(linha, len(colunas)) for linha in linhas[:max_linhas]],
        total_linhas=len(linhas),
        separador=separador,
        codificacao=codificacao,
    )


# ---------- fontes guardadas no pacote ----------


def _pasta_dados(codigo: str) -> Path:
    return PASTA_TESTES / codigo / 'dados'


def listar_fontes(codigo: str) -> list[Fonte]:
    caminho = _pasta_dados(codigo) / 'fontes.json'
    if not caminho.is_file():
        return []
    dados = json.loads(caminho.read_text(encoding='utf-8'))
    return [
        Fonte(**{**f, 'colunas': [Coluna(**c) for c in f['colunas']]})
        for f in dados['fontes']
    ]


def _gravar_fontes(codigo: str, fontes: list[Fonte]) -> None:
    pasta = _pasta_dados(codigo)
    pasta.mkdir(parents=True, exist_ok=True)
    conteudo = {'schema_version': 1, 'fontes': [asdict(f) for f in fontes]}
    temporario = pasta / 'fontes.json.tmp'
    temporario.write_text(
        json.dumps(conteudo, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    temporario.replace(pasta / 'fontes.json')  # troca o arquivo de uma vez só


def _validar_nomes(colunas: list[Coluna]) -> None:
    nomes = [c.exibicao for c in colunas]
    if any(not nome for nome in nomes):
        raise ValueError('Nenhum nome pode ficar vazio.')
    if len({nome.lower() for nome in nomes}) != len(nomes):
        raise ValueError('Os nomes das variáveis devem ser diferentes entre si.')

def _validar_taxa(taxa_hz: float | None) -> float | None:
    if taxa_hz is None:
        return None
    if not math.isfinite(taxa_hz) or taxa_hz <= 0:
        raise ValueError('A taxa de amostragem deve ser um número maior que zero.')
    return float(taxa_hz)


def pasta_dados(codigo: str) -> Path:
    return _pasta_dados(codigo)


def adicionar_fonte(codigo: str, fonte: Fonte) -> None:
    _gravar_fontes(codigo, listar_fontes(codigo) + [fonte])

def importar_csv(
    codigo: str, caminho: Path, nomes: dict[str, str], taxa_hz: float | None = None
) -> Fonte:
    """Copia o CSV (sem alterar) para o pacote e guarda os nomes de exibição e a taxa."""
    if not (PASTA_TESTES / codigo / 'cadastro.json').is_file():
        raise FileNotFoundError(f'A operação {codigo} não existe mais.')

    taxa = _validar_taxa(taxa_hz)
    previa = ler_previa(caminho, max_linhas=0)
    colunas = [
        Coluna(original, (nomes.get(original) or original).strip())
        for original in previa.colunas
    ]
    _validar_nomes(colunas)

    fontes = listar_fontes(codigo)
    numero = max((int(f.id.split('-')[1]) for f in fontes if f.id.startswith('sd-')), default=0) + 1    
    identificador = f'sd-{numero:03d}'
    pasta = _pasta_dados(codigo)
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f'{identificador}.csv'
    shutil.copyfile(caminho, destino)

    fonte = Fonte(
        id=identificador,
        arquivo=destino.name,
        origem=caminho.name,
        importado_em=datetime.now().isoformat(timespec='seconds'),
        separador=previa.separador,
        codificacao=previa.codificacao,
        linhas=previa.total_linhas,
        colunas=colunas,
        taxa_hz=taxa,
    )
    try:
        _gravar_fontes(codigo, fontes + [fonte])
    except Exception:
        destino.unlink(missing_ok=True)  # não deixa um CSV sem registro
        raise
    return fonte

def atualizar_fonte(
    codigo: str, id_fonte: str, nomes: dict[str, str], taxa_hz: float | None
) -> None:
    taxa = _validar_taxa(taxa_hz)
    fontes = listar_fontes(codigo)
    for fonte in fontes:
        if fonte.id == id_fonte:
            for coluna in fonte.colunas:
                coluna.exibicao = (nomes.get(coluna.original) or coluna.original).strip()
            _validar_nomes(fonte.colunas)
            fonte.taxa_hz = taxa
            _gravar_fontes(codigo, fontes)
            return
    raise ValueError('Fonte não encontrada.')

def ler_linhas(codigo: str, fonte: Fonte, limite: int = LIMITE_LINHAS_TABELA) -> list[list[str]]:
    texto = (_pasta_dados(codigo) / fonte.arquivo).read_bytes().decode(fonte.codificacao)
    _, linhas = _separar(texto, fonte.separador)
    return [_ajustar(linha, len(fonte.colunas)) for linha in linhas[:limite]]

# ---------- dados numéricos (para os gráficos do Relatório) ----------


def _converter_coluna(celulas: list[str]) -> list[float | None] | None:
    """Converte uma coluna para números. Devolve None se ela não for numérica."""
    valores: list[float | None] = []
    algum = False
    for celula in celulas:
        celula = celula.strip()
        if not celula:
            valores.append(None)  # célula vazia vira lacuna, não zero
            continue
        try:
            numero = float(celula.replace(',', '.'))  # aceita vírgula decimal
        except ValueError:
            return None
        valores.append(numero if math.isfinite(numero) else None)
        algum = True
    return valores if algum else None


@lru_cache(maxsize=4)
def _numeros(
    caminho: str, modificado_em: int, codificacao: str, separador: str
) -> dict[str, list[float | None]]:
    texto = Path(caminho).read_bytes().decode(codificacao)
    nomes, linhas = _separar(texto, separador)
    ajustadas = [_ajustar(linha, len(nomes)) for linha in linhas]
    resultado = {}
    for nome, celulas in zip(nomes, zip(*ajustadas)):
        valores = _converter_coluna(list(celulas))
        if valores is not None:
            resultado[nome] = valores
    return resultado


def carregar_numeros(codigo: str, fonte: Fonte) -> dict[str, list[float | None]]:
    """Colunas numéricas da fonte, por nome original. Colunas de texto ficam de fora."""
    caminho = _pasta_dados(codigo) / fonte.arquivo
    return _numeros(
        str(caminho), caminho.stat().st_mtime_ns, fonte.codificacao, fonte.separador
    )