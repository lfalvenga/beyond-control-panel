import json
import re
import shutil
import zipfile
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from uuid import uuid4
from datetime import datetime

from modelos import SCHEMA_VERSION, Cadastro, Identificacao, Parametro, Parecer, Tipo

PASTA_TESTES = Path('testes')
EXTENSAO = '.beyondtest'
PASTA_LIXEIRA = PASTA_TESTES / '.lixeira'


class Situacao(str, Enum):
    NOVO = 'novo'
    MESMO_TESTE = 'mesmo_teste'  # mesmo código e mesmo id
    COLISAO = 'colisao'  # mesmo código, mas outro teste (id diferente)
    INVALIDO = 'invalido'


class Acao(str, Enum):
    IMPORTAR = 'importar'
    SUBSTITUIR = 'substituir'
    MANTER_AMBOS = 'manter_ambos'
    PULAR = 'pular'


@dataclass
class Pacote:
    arquivo: Path
    situacao: Situacao
    codigo: str = ''
    cadastro: Cadastro | None = None
    existente: Cadastro | None = None
    erro: str = ''


def _validar_codigo(codigo: str) -> str:
    codigo = codigo.strip()
    if not codigo:
        raise ValueError('Informe o Código do Teste.')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', codigo):
        raise ValueError('O código só pode ter letras, números, - e _.')
    return codigo


def _validar_identificacao(cadastro: Cadastro) -> str:
    """Confere e normaliza código e 'Criado por'; devolve o código."""
    codigo = _validar_codigo(cadastro.identificacao.codigo)
    cadastro.identificacao.codigo = codigo

    criado_por = cadastro.identificacao.criado_por.strip()
    if not criado_por:
        raise ValueError('Informe quem está criando o teste.')
    cadastro.identificacao.criado_por = criado_por

    if cadastro.identificacao.tipo == Tipo.TESTE_ESTATICO:
        cadastro.identificacao.usa_acionamento = True  # teste estático sempre usa o circuito
    return codigo


def _gravar_cadastro(pasta: Path, cadastro: Cadastro) -> None:
    cadastro.schema_version = SCHEMA_VERSION
    temporario = pasta / 'cadastro.json.tmp'
    with open(temporario, 'w', encoding='utf-8') as arquivo:
        json.dump(asdict(cadastro), arquivo, ensure_ascii=False, indent=2)
    temporario.replace(pasta / 'cadastro.json')  # troca o arquivo de uma vez só

def salvar(cadastro: Cadastro, substituir: bool = False) -> Path:
    codigo = _validar_identificacao(cadastro)
    pasta = PASTA_TESTES / codigo

    if pasta.exists():
        if not substituir:
            raise FileExistsError(codigo)
        shutil.rmtree(pasta)

    cadastro.id = str(uuid4())  # salvar cria um teste novo, então ganha id novo
    pasta.mkdir(parents=True)
    _gravar_cadastro(pasta, cadastro)
    return pasta


def atualizar(cadastro: Cadastro) -> str:
    """Grava as alterações de um teste que já existe (mantém id e o resto da pasta)."""
    codigo = _validar_identificacao(cadastro)
    pasta = PASTA_TESTES / codigo
    if not (pasta / 'cadastro.json').is_file():
        raise FileNotFoundError(f'O teste {codigo} não existe mais.')
    if not cadastro.id:
        cadastro.id = str(uuid4())  # teste antigo, de antes do id
    _gravar_cadastro(pasta, cadastro)
    return codigo


def _cadastro_de_dict(dados: dict) -> Cadastro:
    ident = dict(dados['identificacao'])
    ident['tipo'] = Tipo(ident.get('tipo', Tipo.TESTE_ESTATICO))
    return Cadastro(
        schema_version=dados['schema_version'],
        id=dados.get('id', ''),
        identificacao=Identificacao(**ident),
        ficha=[
            Parametro(**{**p, 'parecer': Parecer(p['parecer'])})
            for p in dados['ficha']
        ],
    )


def carregar(codigo: str) -> Cadastro:
    caminho = PASTA_TESTES / codigo / 'cadastro.json'
    with open(caminho, encoding='utf-8') as arquivo:
        return _cadastro_de_dict(json.load(arquivo))


def listar() -> list[Cadastro]:
    if not PASTA_TESTES.exists():
        return []
    testes = []
    for pasta in sorted(PASTA_TESTES.iterdir()):
        if not (pasta / 'cadastro.json').is_file():
            continue
        try:
            testes.append(carregar(pasta.name))
        except (OSError, ValueError, KeyError, TypeError):
            continue  # cadastro ilegível: ignora em vez de quebrar a lista
    return testes


def exportar(codigo: str, destino: Path) -> Path:
    pasta = PASTA_TESTES / _validar_codigo(codigo)
    if not (pasta / 'cadastro.json').is_file():
        raise FileNotFoundError(f'Teste {codigo} não encontrado.')

    try:
        with zipfile.ZipFile(destino, 'w', zipfile.ZIP_DEFLATED) as pacote:
            for arquivo in sorted(pasta.rglob('*')):
                if not arquivo.is_file() or arquivo.resolve() == destino.resolve():
                    continue
                nome = arquivo.relative_to(pasta).as_posix()
                pacote.write(arquivo, arcname=f'{codigo}/{nome}')
    except Exception:
        destino.unlink(missing_ok=True)  # não deixa um pacote incompleto
        raise
    return destino


# ---------- importação ----------


def _invalido(arquivo: Path, erro: str) -> Pacote:
    return Pacote(arquivo, Situacao.INVALIDO, erro=erro)


def verificar_pacote(arquivo: Path) -> Pacote:
    """Confere um .beyondtest SEM gravar nada e diz em que situação ele está."""
    try:
        with zipfile.ZipFile(arquivo) as pacote:
            topos = set()
            for nome in pacote.namelist():
                partes = PurePosixPath(nome).parts
                if '\\' in nome or nome.startswith('/') or '..' in partes or not partes:
                    return _invalido(arquivo, 'O pacote contém caminhos inválidos.')
                topos.add(partes[0])

            if len(topos) != 1:
                return _invalido(arquivo, 'O pacote deve ter uma única pasta de teste.')
            codigo = topos.pop()
            if not re.fullmatch(r'[A-Za-z0-9_-]+', codigo):
                return _invalido(arquivo, 'O código do pacote é inválido.')

            try:
                dados = json.loads(pacote.read(f'{codigo}/cadastro.json'))
            except KeyError:
                return _invalido(arquivo, 'O pacote não tem cadastro.json.')

            if dados.get('schema_version', 0) > SCHEMA_VERSION:
                return _invalido(
                    arquivo, 'Pacote gerado por uma versão mais nova do aplicativo.'
                )
            cadastro = _cadastro_de_dict(dados)
    except (zipfile.BadZipFile, OSError):
        return _invalido(arquivo, 'Arquivo inválido ou corrompido.')
    except (ValueError, KeyError, TypeError):
        return _invalido(arquivo, 'O cadastro do pacote está ilegível.')

    if cadastro.identificacao.codigo != codigo:
        return _invalido(arquivo, 'O código do cadastro não bate com a pasta do pacote.')

    if not (PASTA_TESTES / codigo).exists():
        return Pacote(arquivo, Situacao.NOVO, codigo, cadastro)

    try:
        existente = carregar(codigo)
    except (OSError, ValueError, KeyError, TypeError):
        existente = None
    mesmo = existente is not None and existente.id != '' and existente.id == cadastro.id
    situacao = Situacao.MESMO_TESTE if mesmo else Situacao.COLISAO
    return Pacote(arquivo, situacao, codigo, cadastro, existente)


def _codigo_livre(codigo: str) -> str:
    n = 2
    while (PASTA_TESTES / f'{codigo}-{n}').exists():
        n += 1
    return f'{codigo}-{n}'


def _reescrever_cadastro(pasta: Path, codigo: str, novo_id: bool) -> None:
    caminho = pasta / 'cadastro.json'
    dados = json.loads(caminho.read_text(encoding='utf-8'))
    dados['identificacao']['codigo'] = codigo
    if novo_id:
        dados['id'] = str(uuid4())
    caminho.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2), encoding='utf-8'
    )


def importar_pacote(pacote: Pacote, acao: Acao) -> str:
    """Grava o pacote e devolve o código com que ele ficou salvo."""
    codigo = pacote.codigo
    PASTA_TESTES.mkdir(exist_ok=True)
    temporaria = PASTA_TESTES / f'.importando-{uuid4().hex}'
    try:
        with zipfile.ZipFile(pacote.arquivo) as zip_:
            zip_.extractall(temporaria)
        extraida = temporaria / codigo
        destino = PASTA_TESTES / codigo
        antigo = None

        if acao == Acao.MANTER_AMBOS:
            codigo = _codigo_livre(codigo)
            # uma cópia do MESMO teste precisa de id novo; um teste diferente mantém o seu
            _reescrever_cadastro(extraida, codigo, pacote.situacao == Situacao.MESMO_TESTE)
            destino = PASTA_TESTES / codigo
        elif destino.exists():
            if acao != Acao.SUBSTITUIR:
                raise FileExistsError(f'Já existe um teste {codigo}.')
            antigo = temporaria / 'antigo'
            destino.rename(antigo)  # guarda o antigo até o novo estar no lugar

        try:
            extraida.rename(destino)
        except OSError:
            if antigo is not None:
                antigo.rename(destino)  # deu errado: devolve o antigo
            raise
        return codigo
    finally:
        shutil.rmtree(temporaria, ignore_errors=True)

def excluir(codigo: str) -> Path:
    """Move o teste para a lixeira (testes/.lixeira). Não apaga nada de vez."""
    pasta = PASTA_TESTES / _validar_codigo(codigo)
    if not (pasta / 'cadastro.json').is_file():
        raise FileNotFoundError(f'Teste {codigo} não encontrado.')

    PASTA_LIXEIRA.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime('%Y%m%d-%H%M%S')
    destino = PASTA_LIXEIRA / f'{codigo}-{carimbo}-{uuid4().hex[:4]}'
    shutil.move(str(pasta), str(destino))
    return destino