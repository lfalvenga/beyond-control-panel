class Estado:
    """O que o app inteiro precisa saber ao mesmo tempo."""

    def __init__(self) -> None:
        self.reiniciar()

    def reiniciar(self) -> None:
        self.teste_ativo: str | None = None  # operação em uso (Acionamento, Log, Relatório)
        self.em_edicao: str | None = None  # teste aberto no Cadastro (None = teste novo)
        self._ao_mudar_ativo: list = []
        self._ao_mudar_edicao: list = []
        self._ao_mudar_lista: list = []
        self._ao_mudar_dados: list = []
        self.ir = lambda nome: None  # o main.py troca por uma navegação de verdade
        # o Cadastro troca por uma função que avisa de alterações não salvas
        self.guarda_edicao = lambda codigo: self.editar(codigo, forcar=True)

    def ao_mudar_ativo(self, funcao) -> None:
        self._ao_mudar_ativo.append(funcao)

    def ao_mudar_edicao(self, funcao) -> None:
        self._ao_mudar_edicao.append(funcao)

    def ao_mudar_lista(self, funcao) -> None:
        self._ao_mudar_lista.append(funcao)

    def ao_mudar_dados(self, funcao) -> None:
        self._ao_mudar_dados.append(funcao)

    def ativar(self, codigo: str | None, forcar: bool = False) -> None:
        if codigo == self.teste_ativo and not forcar:
            return
        self.teste_ativo = codigo
        for funcao in list(self._ao_mudar_ativo):
            funcao()

    def editar(self, codigo: str | None, forcar: bool = False) -> None:
        if codigo == self.em_edicao and not forcar:
            return
        self.em_edicao = codigo
        for funcao in list(self._ao_mudar_edicao):
            funcao()

    def pedir_edicao(self, codigo: str | None) -> None:
        """Pede para abrir `codigo` no Cadastro (None = teste novo).

        Passa pela guarda, que pode perguntar antes de descartar alterações."""
        self.guarda_edicao(codigo)

    def lista_mudou(self) -> None:
        for funcao in list(self._ao_mudar_lista):
            funcao()

    def dados_mudaram(self) -> None:
        """Os dados (CSVs importados, nomes das variáveis) da operação ativa mudaram."""
        for funcao in list(self._ao_mudar_dados):
            funcao()


estado = Estado()